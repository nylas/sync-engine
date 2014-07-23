<?php

/**
 * This a simple example lint engine which just applies the
 * @{class:ArcanistPyLintLinter} to any Python files. For a more complex
 * example, see @{class:PhutilLintEngine}.
 *
 * @group linter
 */
final class InboxServerLintEngine extends ArcanistLintEngine {

  public function buildLinters() {

    // This is a list of paths which the user wants to lint. Either they
    // provided them explicitly, or arc figured them out from a commit or set
    // of changes. The engine needs to return a list of ArcanistLinter objects,
    // representing the linters which should be run on these files.
    $paths = $this->getPaths();
    //echo('Foobar');
    // $paths = ['./src/inbox'];

    // The ArcanistPyLintLinter runs "PyLint" (an open source python linter) on
    // files you give it. There are several linters available by default like
    // this one which you can use out of the box, or you can write your own.
    // Linters are responsible for actually analyzing the contents of a file
    // and raising warnings and errors.
    $flake8_linter = new ArcanistFlake8Linter();
    $pylint_linter = new MGArcanistPyLintLinter();

    // Remove any paths that don't exist before we add paths to linters. We want
    // to do this for linters that operate on file contents because the
    // generated list of paths will include deleted paths when a file is
    // removed.
    foreach ($paths as $key => $path) {
      if (!$this->pathExists($path)) {
        unset($paths[$key]);
      }
    }

    foreach ($paths as $path) {
      if (!preg_match('/\.py$/', $path)) {
        // This isn't a python file, so don't try to apply the PyLint linter
        // to it.
        continue;
      }

      if (preg_match('@^externals/@', $path)) {
        // This is just an example of how to exclude a path so it doesn't get
        // linted. If you put third-party code in an externals/ directory, you
        // can just have your lint engine ignore it.
        continue;
      }

      // Add the path, to tell the linter it should examine the source code
      // to try to find problems.
      $pylint_linter->addPath($path);
      $flake8_linter->addPath($path);
    }

    // We only built one linter, but you can build more than one (e.g., a
    // Javascript linter for JS), and return a list of linters to execute. You
    // can also add a path to more than one linter (for example, if you want
    // to run a Python linter and a more general text linter on every .py file).

    return array(
      $pylint_linter,
      $flake8_linter,
    );
  }

}
