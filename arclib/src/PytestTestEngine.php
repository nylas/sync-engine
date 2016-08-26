<?php

/**
 * Very basic 'py.test' unit test engine wrapper.
 *
 * @group unitrun
 */
final class PytestTestEngine extends ArcanistUnitTestEngine {

  public function run() {
    $working_copy = $this->getWorkingCopy();
    $project_root = $working_copy->getProjectRoot();

    $test_output = $project_root . '/tests/output';
    $cover_output = $project_root . '/tests/coverage';

    $future = $this->buildTestFuture($test_output, $cover_output);
    while (!$future->isReady()) {
      $stdout = $future->readStdout();
      print $stdout;
    }

    $future->resolvex();

    return $this->parseTestResults($test_output, $cover_output);
  }

  public function buildTestFuture($test_output, $cover_output) {
    $paths = $this->getPaths();

    # We want to run the tests inside the VM.
    # `vagrant ssh -c` will return the exit code of whatever command you pass,
    # but we need it to always return 0. Hence the `|| true`.

    # Set SYNC_ENGINE_REPO_VAGRANT_PATH to the location of the sync engine repo
    # within your VM. By default this is /vagrant via stock setup.sh but you
    # may move it elsewhere! TODO just use a symlink for this later

    $se_path = getenv('SYNC_ENGINE_REPO_VAGRANT_PATH');

    if (!$se_path) {
      $se_path = '/vagrant';
    }

    $cmd_line = csprintf("vagrant ssh -c \"export NYLAS_ENV=test; cd $se_path; coverage run --source $se_path/inbox -m py.test --junitxml $se_path/tests/output $se_path/tests; coverage xml -i -o $se_path/tests/coverage; true\"");

    return new ExecFuture('%C', $cmd_line);
  }

  public function parseTestResults($test_output, $cover_output) {
    $parser = new ArcanistXUnitTestResultParser();
    $results = $parser->parseTestResults(
      Filesystem::readFile($test_output));

    $coverage_report = $this->readCoverage($cover_output);
    foreach ($results as $result) {
        $result->setCoverage($coverage_report);
    }

    return $results;
  }

  public function readCoverage($path) {
    $coverage_data = Filesystem::readFile($path);
    if (empty($coverage_data)) {
       return array();
    }

    $coverage_dom = new DOMDocument();
    $coverage_dom->loadXML($coverage_data);

    $paths = $this->getPaths();
    $reports = array();
    $classes = $coverage_dom->getElementsByTagName("class");

    foreach ($classes as $class) {
      // filename is actually python module path with ".py" at the end,
      // e.g.: tornado.web.py
      $relative_path = explode(".", $class->getAttribute("filename"));
      array_pop($relative_path);
      $relative_path = implode("/", $relative_path);

      // first we check if the path is a directory (a Python package), if it is
      // set relative and absolute paths to have __init__.py at the end.
      $absolute_path = Filesystem::resolvePath($relative_path);
      if (is_dir($absolute_path)) {
        $relative_path .= "/__init__.py";
        $absolute_path .= "/__init__.py";
      }

      // then we check if the path with ".py" at the end is file (a Python
      // submodule), if it is - set relative and absolute paths to have
      // ".py" at the end.
      if (is_file($absolute_path.".py")) {
        $relative_path .= ".py";
        $absolute_path .= ".py";
      }

      if (!file_exists($absolute_path)) {
        continue;
      }

      if (!in_array($relative_path, $paths)) {
        continue;
      }

      // get total line count in file
      $line_count = count(file($absolute_path));

      $coverage = "";
      $start_line = 1;
      $lines = $class->getElementsByTagName("line");
      for ($ii = 0; $ii < $lines->length; $ii++) {
        $line = $lines->item($ii);

        $next_line = intval($line->getAttribute("number"));
        for ($start_line; $start_line < $next_line; $start_line++) {
            $coverage .= "N";
        }

        if (intval($line->getAttribute("hits")) == 0) {
            $coverage .= "U";
        }
        else if (intval($line->getAttribute("hits")) > 0) {
            $coverage .= "C";
        }

        $start_line++;
      }

      if ($start_line < $line_count) {
        foreach (range($start_line, $line_count) as $line_num) {
          $coverage .= "N";
        }
      }

      $reports[$relative_path] = $coverage;
    }

    return $reports;
  }
}
