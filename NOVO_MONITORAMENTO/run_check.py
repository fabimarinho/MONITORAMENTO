import json
from config import load_settings
from check import SiteChecker

if __name__ == '__main__':
    settings = load_settings()
    checker = SiteChecker(settings)
    result = checker.perform_check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
