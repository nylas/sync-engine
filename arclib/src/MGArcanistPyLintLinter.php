<?php
final class MGArcanistPyLintLinter extends ArcanistExternalLinter {
  private $config;

  public function getInfoName() {
    return 'PyLint';
  }

  public function getInfoURI() {
    return 'http://www.pylint.org/';
  }

  public function getInfoDescription() {
    return pht(
      'PyLint is a Python source code analyzer which looks for '.
      'programming errors, helps enforcing a coding standard and '.
      'sniffs for some code smells.');
  }

  public function getLinterName() {
    return 'PyLint';
  }

  public function getLinterConfigurationName() {
    return 'pylint';
  }

  public function getDefaultBinary() {
    putenv("PYTHONPATH=inbox");
    return 'pylint';
  }

  public function getVersion() {
    list($stdout) = execx('%C --version', $this->getExecutableCommand());

    $matches = array();
    $regex = '/^pylint (?P<version>\d+\.\d+\.\d+),/';
    if (preg_match($regex, $stdout, $matches)) {
      return $matches['version'];
    } else {
      return false;
    }
  }

  public function getInstallInstructions() {
    return pht(
      'Install PyLint using `%s`.',
      'pip install pylint');
  }

  public function shouldExpectCommandErrors() {
    return true;
  }

  public function getLinterConfigurationOptions() {
    $options = array(
      'pylint.config' => array(
        'type' => 'optional string',
        'help' => pht('Pass in a custom configuration file path.'),
      ),
    );

    return $options + parent::getLinterConfigurationOptions();
  }

  public function setLinterConfigurationValue($key, $value) {
    switch ($key) {
      case 'pylint.config':
        $this->config = $value;
        return;

      default:
        return parent::setLinterConfigurationValue($key, $value);
    }
  }

  protected function getMandatoryFlags() {
    $options = array();

    $options[] = '--reports=no';
    $options[] = '--msg-template="{line}|{column}|{msg_id}|{symbol}|{msg}"';
    $options[] = '-d all -e w0631';

    // Specify an `--rcfile`, either absolute or relative to the project root.
    // Stupidly, the command line args above are overridden by rcfile, so be
    // careful.
    $config = $this->config;
    if ($config !== null) {
      $options[] = '--rcfile='.$config;
    }

    return $options;
  }

  protected function getDefaultFlags() {
    $options = array();

    $installed_version = $this->getVersion();
    $minimum_version = '1.0.0';
    if (version_compare($installed_version, $minimum_version, '<')) {
      throw new ArcanistMissingLinterException(
        pht(
          '%s is not compatible with the installed version of pylint. '.
          'Minimum version: %s; installed version: %s.',
          __CLASS__,
          $minimum_version,
          $installed_version));
    }

    return $options;
  }

  protected function parseLinterOutput($path, $err, $stdout, $stderr) {
    if ($err === 32) {
      // According to `man pylint` the exit status of 32 means there was a
      // usage error. That's bad, so actually exit abnormally.
      return false;
    }

    list($stdout) = execx('pylint -d all -e w0631 inbox');
    $lines = phutil_split_lines($stdout, false);
    $messages = array();

    foreach ($lines as $line) {
      $matches = explode('|', $line, 5);

      if (count($matches) < 5) {
        continue;
      }

      $message = id(new ArcanistLintMessage())
        ->setPath($path)
        ->setLine($matches[0])
        ->setChar($matches[1])
        ->setCode($matches[2])
        ->setSeverity($this->getLintMessageSeverity($matches[2]))
        ->setName(ucwords(str_replace('-', ' ', $matches[3])))
        ->setDescription($matches[4]);

      $messages[] = $message;
    }

    return $messages;
  }

  protected function getDefaultMessageSeverity($code) {
    switch (substr($code, 0, 1)) {
      case 'R':
      case 'C':
        return ArcanistLintSeverity::SEVERITY_ADVICE;
      case 'W':
        return ArcanistLintSeverity::SEVERITY_WARNING;
      case 'E':
      case 'F':
        return ArcanistLintSeverity::SEVERITY_ERROR;
      default:
        return ArcanistLintSeverity::SEVERITY_DISABLED;
    }
  }

  protected function getLintCodeFromLinterConfigurationKey($code) {
    if (!preg_match('/^(R|C|W|E|F)\d{4}$/', $code)) {
      throw new Exception(
        pht(
          'Unrecognized lint message code "%s". Expected a valid Pylint '.
          'lint code like "%s", or "%s", or "%s".',
          $code,
          'C0111',
          'E0602',
          'W0611'));
    }

    return $code;
  }
}
