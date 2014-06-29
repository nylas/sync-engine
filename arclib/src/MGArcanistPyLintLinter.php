<?php

/**
 * Uses "PyLint" to detect various errors in Python code. To use this linter,
 * you must install pylint and configure which codes you want to be reported as
 * errors, warnings and advice.
 *
 * You should be able to install pylint with ##sudo easy_install pylint##. If
 * your system is unusual, you can manually specify the location of pylint and
 * its dependencies by configuring these keys in your .arcconfig:
 *
 *   lint.pylint.prefix
 *   lint.pylint.logilab_astng.prefix
 *   lint.pylint.logilab_common.prefix
 *
 * You can specify additional command-line options to pass to PyLint by
 * setting ##lint.pylint.options##. You may also specify a list of additional
 * entries for PYTHONPATH with ##lint.pylint.pythonpath##. Those can be
 * absolute or relative to the project root.
 *
 * If you have a PyLint rcfile, specify its path with
 * ##lint.pylint.rcfile##. It can be absolute or relative to the project
 * root. Be sure not to define ##output-format##, or if you do, set it to
 * ##text##.
 *
 * Specify which PyLint messages map to which Arcanist messages by defining
 * the following regular expressions:
 *
 *   lint.pylint.codes.error
 *   lint.pylint.codes.warning
 *   lint.pylint.codes.advice
 *
 * The regexps are run in that order; the first to match determines which
 * Arcanist severity applies, if any. For example, to capture all PyLint
 * "E...." errors as Arcanist errors, set ##lint.pylint.codes.error## to:
 *
 *    ^E.*
 *
 * You can also match more granularly:
 *
 *    ^E(0001|0002)$
 *
 * According to ##man pylint##, there are 5 kind of messages:
 *
 *   (C) convention, for programming standard violation
 *   (R) refactor, for bad code smell
 *   (W) warning, for python specific problems
 *   (E) error, for probable bugs in the code
 *   (F) fatal, if an error occurred which prevented pylint from
 *       doing further processing.
 *
 * @group linter
 */
final class MGArcanistPyLintLinter extends ArcanistLinter {

  private function getMessageCodeSeverity($code) {

    $config = $this->getEngine()->getConfigurationManager();

    $error_regexp   =
      $config->getConfigFromAnySource('lint.pylint.codes.error');
    $warning_regexp =
      $config->getConfigFromAnySource('lint.pylint.codes.warning');
    $advice_regexp  =
      $config->getConfigFromAnySource('lint.pylint.codes.advice');

    if (!$error_regexp && !$warning_regexp && !$advice_regexp) {
      throw new ArcanistUsageException(
        "You are invoking the PyLint linter but have not configured any of ".
        "'lint.pylint.codes.error', 'lint.pylint.codes.warning', or ".
        "'lint.pylint.codes.advice'. Consult the documentation for ".
        "MGArcanistPyLintLinter.");
    }

    $code_map = array(
      ArcanistLintSeverity::SEVERITY_ERROR    => $error_regexp,
      ArcanistLintSeverity::SEVERITY_WARNING  => $warning_regexp,
      ArcanistLintSeverity::SEVERITY_ADVICE   => $advice_regexp,
    );

    foreach ($code_map as $sev => $codes) {
      if ($codes === null) {
        continue;
      }
      if (!is_array($codes)) {
        $codes = array($codes);
      }
      foreach ($codes as $code_re) {
        if (preg_match("/{$code_re}/", $code)) {
          return $sev;
        }
      }
    }

    // If the message code doesn't match any of the provided regex's,
    // then just disable it.
    return ArcanistLintSeverity::SEVERITY_DISABLED;
  }

  private function getPyLintPath() {
    $pylint_bin = "pylint";

    // Use the PyLint prefix specified in the config file
    $config = $this->getEngine()->getConfigurationManager();
    $prefix = $config->getConfigFromAnySource('lint.pylint.prefix');
    if ($prefix !== null) {
      $pylint_bin = $prefix."/bin/".$pylint_bin;
    }

    if (!Filesystem::pathExists($pylint_bin)) {

      list($err) = exec_manual('which %s', $pylint_bin);
      if ($err) {
        throw new ArcanistUsageException(
          "PyLint does not appear to be installed on this system. Install it ".
          "(e.g., with 'sudo easy_install pylint') or configure ".
          "'lint.pylint.prefix' in your .arcconfig to point to the directory ".
          "where it resides.");
      }
    }

    return $pylint_bin;
  }

  private function getPyLintPythonPath() {
    // Get non-default install locations for pylint and its dependencies
    // libraries.
    $config = $this->getEngine()->getConfigurationManager();
    $prefixes = array(
      $config->getConfigFromAnySource('lint.pylint.prefix'),
      $config->getConfigFromAnySource('lint.pylint.logilab_astng.prefix'),
      $config->getConfigFromAnySource('lint.pylint.logilab_common.prefix'),
    );

    // Add the libraries to the python search path
    $python_path = array();
    foreach ($prefixes as $prefix) {
      if ($prefix !== null) {
        $python_path[] = $prefix.'/lib/python2.7/site-packages';
        $python_path[] = $prefix.'/lib/python2.7/dist-packages';
        $python_path[] = $prefix.'/lib/python2.6/site-packages';
        $python_path[] = $prefix.'/lib/python2.6/dist-packages';
      }
    }

    $working_copy = $this->getEngine()->getWorkingCopy();
    $config_paths = $config->getConfigFromAnySource('lint.pylint.pythonpath');
    if ($config_paths !== null) {
      foreach ($config_paths as $config_path) {
        if ($config_path !== null) {
          $python_path[] =
            Filesystem::resolvePath($config_path,
                                    $working_copy->getProjectRoot());
        }
      }
    }

    $python_path[] = '';
    return implode(":", $python_path);
  }

  private function getPyLintOptions() {
    // '-rn': don't print lint report/summary at end
    // '-iy': show message codes for lint warnings/errors
    $options = array('-rn');

    $working_copy = $this->getEngine()->getWorkingCopy();
    $config = $this->getEngine()->getConfigurationManager();

    // Specify an --rcfile, either absolute or relative to the project root.
    // Stupidly, the command line args above are overridden by rcfile, so be
    // careful.
    $rcfile = $config->getConfigFromAnySource('lint.pylint.rcfile');
    if ($rcfile !== null) {
      $rcfile = Filesystem::resolvePath(
                   $rcfile,
                   $working_copy->getProjectRoot());
      $options[] = csprintf('--rcfile=%s', $rcfile);
    }

    // Add any options defined in the config file for PyLint
    $config_options = $config->getConfigFromAnySource('lint.pylint.options');
    if ($config_options !== null) {
      $options = array_merge($options, $config_options);
    }

    return implode(" ", $options);
  }

  public function getLinterName() {
    return 'PyLint';
  }

  public function lintPath($path) {
    $pylint_bin = $this->getPyLintPath();
    $python_path = $this->getPyLintPythonPath();
    $options = $this->getPyLintOptions();
    $path_on_disk = $this->getEngine()->getFilePathOnDisk($path);

    try {
      list($stdout, $_) = execx(
        '/usr/bin/env PYTHONPATH=%s$PYTHONPATH %s %C %s',
        $python_path,
        $pylint_bin,
        $options,
        $path_on_disk);
    } catch (CommandException $e) {
      if ($e->getError() == 32) {
        // According to ##man pylint## the exit status of 32 means there was a
        // usage error. That's bad, so actually exit abnormally.
        throw $e;
      } else {
        // The other non-zero exit codes mean there were messages issued,
        // which is expected, so don't exit.
        $stdout = $e->getStdout();
      }
    }

    $lines = explode("\n", $stdout);
    $messages = array();
    foreach ($lines as $line) {
      $matches = null;
      if (!preg_match(
              '/([A-Z]\d+): *(\d+)(?:|,\d*): *(.*)$/',
              $line, $matches)) {
        continue;
      }
      foreach ($matches as $key => $match) {
        $matches[$key] = trim($match);
      }

      $message = new ArcanistLintMessage();
      $message->setPath($path);
      $message->setLine($matches[2]);
      $message->setCode($matches[1]);
      $message->setName($this->getLinterName()." ".$matches[1]);
      $message->setDescription($matches[3]);
      $message->setSeverity($this->getMessageCodeSeverity($matches[1]));
      $this->addLintMessage($message);
    }
  }

}
