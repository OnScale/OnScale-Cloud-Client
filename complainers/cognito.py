from renag import Complainer, Severity


class CognitoComplainer(Complainer):
    """Detected cognito token, very dangerous to commit these, remove immediately"""
    capture = r"\w{8}-\w{4}-\w{4}-\w{4}-\w{12}_[0-9]{13}_\w{8}-\w{4}-\w{4}-\w{4}-\w{12}"
    severity = Severity.CRITICAL
    glob = ["*.py", "*.rs", "*.yaml", "*.json", ".env", "*.yml", "*.java", "*.ts", "*.js"]
    regex_options = 0  # For speed
