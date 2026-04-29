"""源码调试时使用的 OOPZ 账号密码登录凭据提取入口。"""

from __future__ import annotations

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from oopz_sdk.auth.password_login import main


if __name__ == "__main__":
    raise SystemExit(main())
