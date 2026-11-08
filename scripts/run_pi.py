import sys
import subprocess

HOSTKEY = "SHA256:pCOwu3qhx/euWwu3gF8dIHRvtmQ50uz3bmB5xFufVdw"
PLINK = r"C:\Program Files\PuTTY\plink.exe"
PASS = "raspscreen#1234"
USER = "raspscreen"
HOST = "192.168.0.17"

cmd = " ".join(sys.argv[1:])
res = subprocess.run([PLINK, "-batch", "-hostkey", HOSTKEY, "-pw", PASS, f"{USER}@{HOST}", cmd], capture_output=True, text=True)
if res.stdout:
    print(res.stdout, end="")
if res.stderr:
    print(res.stderr, file=sys.stderr, end="")
sys.exit(res.returncode)
