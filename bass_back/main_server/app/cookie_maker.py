import json
from typing import Any

RAW_JSON_TEXT: str = r'''
[
[
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.806842,
    "hostOnly": false,
    "httpOnly": false,
    "name": "__Secure-1PAPISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "taCHlYCRLeU6n9Ch/A_eVop3hkwm5QaSyR",
    "id": 1
},
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.807323,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "g.a0006Ah_99HxoxGq09jXYCLn7sAq3VEIdd5VEL7z6h3DHDpC0MNGebZ78mxrTAYMcfzoOzCiQgACgYKASESARcSFQHGX2Mi6pUTjrfNEtznghhEZ2K4hRoVAUF8yKrbpvBcJGyK0_79XyLvTXY40076",
    "id": 2
},
{
    "domain": ".youtube.com",
    "expirationDate": 1801890199.331038,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSIDCC",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzUQzoc79PHyRum6S1ajkio1ZOEV3xwgeLxVOXiVzY2-OA3dHb2oZrmSgTumPz-btrw8qw",
    "id": 3
},
{
    "domain": ".youtube.com",
    "expirationDate": 1801890190.353374,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-1PSIDTS",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "sidts-CjIB7I_69BCeaawUv98d6b7dG98-xp60lmTpCDBLNBB2zh9TFcUlWuVb3lTCf7zAzuv8vhAA",
    "id": 4
},
{
    "domain": ".youtube.com",
    "expirationDate": 1804501320.183145,
    "hostOnly": false,
    "httpOnly": false,
    "name": "__Secure-3PAPISID",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "taCHlYCRLeU6n9Ch/A_eVop3hkwm5QaSyR",
    "id": 5
},
{
    "domain": ".youtube.com",
    "expirationDate": 1804501320.18359,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSID",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "g.a0006Ah_99HxoxGq09jXYCLn7sAq3VEIdd5VEL7z6h3DHDpC0MNG0dMN8diJkrMs6ITe8L8EAQACgYKAa4SARcSFQHGX2Miflax33nsTkymX2KEb6k0AhoVAUF8yKr40c0_B1S_GoIeoosYVNSm0076",
    "id": 6
},
{
    "domain": ".youtube.com",
    "expirationDate": 1801890199.331083,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSIDCC",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzX7xjE63duroFSThjP8dw_NDViQQQLlB4JzO3vJrfgZu4yBiLJDlehYM2My7e-L-EaUag",
    "id": 7
},
{
    "domain": ".youtube.com",
    "expirationDate": 1801890190.353531,
    "hostOnly": false,
    "httpOnly": true,
    "name": "__Secure-3PSIDTS",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "sidts-CjIB7I_69BCeaawUv98d6b7dG98-xp60lmTpCDBLNBB2zh9TFcUlWuVb3lTCf7zAzuv8vhAA",
    "id": 8
},
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.806745,
    "hostOnly": false,
    "httpOnly": false,
    "name": "APISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "1VQASbYUte2Tmx5x/AP1tHd5ivC9CYcJKo",
    "id": 9
},
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.806571,
    "hostOnly": false,
    "httpOnly": true,
    "name": "HSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "Am_IwwgS43OWIf6VZ",
    "id": 10
},
{
    "domain": ".youtube.com",
    "expirationDate": 1794901501.528645,
    "hostOnly": false,
    "httpOnly": true,
    "name": "LOGIN_INFO",
    "path": "/",
    "sameSite": "no_restriction",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AFmmF2swRQIgbw-_JWRd27UljxOGgY59Zu6kP3fvY_XOEa0DNSVJSX4CIQCVRG5yk5Nd1xMXXHKg7pDdvLObmS4NQf3jZUvna0VhcQ:QUQ3MjNmeVZ0Vy1hZ3BtdU5BRXExbjBTcGtLT25aczJ3c0YzaGZxWnJYaG5DMlAyWjVISlNiTElVSXROSi00bUxrUHJkcTVLNGkwYTJlMi1fdFNBS1VseWtib1VMVF9GYi1wdXNSUnhzWHdWS2JSVEdUY2FVYUpldWYyZEIwb2NOc1drUmtwNXlPM2RZZW9sZVZJUEtrOW9LbkdNN3NhSllB",
    "id": 11
},
{
    "domain": ".youtube.com",
    "expirationDate": 1804914187.95992,
    "hostOnly": false,
    "httpOnly": false,
    "name": "PREF",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "f7=4100&tz=Asia.Seoul&f4=4010000&f5=20000&f6=80",
    "id": 12
},
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.806795,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SAPISID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "taCHlYCRLeU6n9Ch/A_eVop3hkwm5QaSyR",
    "id": 13
},
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.807277,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "g.a0006Ah_99HxoxGq09jXYCLn7sAq3VEIdd5VEL7z6h3DHDpC0MNG2BZvd2cWBWHYZKN1fs6kjQACgYKAZYSARcSFQHGX2MiVmfkkrJt4q2Z3Ime1X1C3RoVAUF8yKpZkBB_pSmJ7nPUKD1lY2_R0076",
    "id": 14
},
{
    "domain": ".youtube.com",
    "expirationDate": 1801890199.330918,
    "hostOnly": false,
    "httpOnly": false,
    "name": "SIDCC",
    "path": "/",
    "sameSite": "unspecified",
    "secure": false,
    "session": false,
    "storeId": "0",
    "value": "AKEyXzXNdEIZqp1ESjTMbRrhwATX2j-rWfGJWNvn-sUD04IWof91oUANucvvvF7_bJtUCP4cjg",
    "id": 15
},
{
    "domain": ".youtube.com",
    "expirationDate": 1803963005.806693,
    "hostOnly": false,
    "httpOnly": true,
    "name": "SSID",
    "path": "/",
    "sameSite": "unspecified",
    "secure": true,
    "session": false,
    "storeId": "0",
    "value": "AzCK1Q_xPbA2fQsoE",
    "id": 16
}
]
]
'''

def _flatten_cookie_items(data: Any) -> list[dict[str, Any]]:
    """
    data가
      - [ {..}, {..} ] 이면 그대로
      - [ [ {..}, {..} ] ] 처럼 1겹 더 감싸져도 평탄화
      - 중간에 list가 섞여도 평탄화
    """
    out: list[dict[str, Any]] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            out.append(x)
            return
        if isinstance(x, list):
            for y in x:
                walk(y)
            return
        # 그 외 타입은 무시

    walk(data)
    return out

def json_to_cookies_txt(*, cookies: list[dict[str, Any]], output_path: str = "cookies.txt") -> None:
    lines: list[str] = ["# Netscape HTTP Cookie File"]

    written: int = 0
    skipped: int = 0

    for c in cookies:
        # 필수 키가 없으면 스킵
        if "domain" not in c or "name" not in c or "value" not in c:
            skipped += 1
            continue

        domain: str = str(c["domain"])
        include_subdomains: str = "TRUE" if not bool(c.get("hostOnly", False)) else "FALSE"
        path: str = str(c.get("path", "/"))
        secure: str = "TRUE" if bool(c.get("secure", False)) else "FALSE"

        expires_raw: float | int = c.get("expirationDate", 0)
        try:
            expires: int = int(expires_raw)  # 소수점 버림
        except Exception:
            expires = 0

        name: str = str(c["name"])
        value: str = str(c["value"])

        lines.append("\t".join([domain, include_subdomains, path, secure, str(expires), name, value]))
        written += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ cookies.txt 생성 완료: {output_path}")
    print(f"   - written={written}, skipped={skipped}")

if __name__ == "__main__":
    parsed: Any = json.loads(RAW_JSON_TEXT)
    cookies: list[dict[str, Any]] = _flatten_cookie_items(parsed)
    json_to_cookies_txt(cookies=cookies, output_path="cookies.txt")
