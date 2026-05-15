from __future__ import annotations

import base64
import zlib


_XOR_KEY = b"oopz-sdk-login-bundle"


_CLIENT_SIGNING_KEY_DATA = [
    "==Q_DtNVtExysCJnNVegM6WBT-",
    "l6izAbyElxe7S2q3CuDPRR6S5mS2QPLCII54AteKkL5LtDG4TedQVVDh9b7LS1O9JWdshvkh6Nxv",
    "8i7kLPngaSlkyFBkrFzPQrEKIQHhg2tgHUqO7yyYkxymTjphKT1mRlBjfuOfBhE-rDH0u6fosVT7",
    "Pwc3cwTKNNImuQgZuPVVUf-",
    "j4VqDf9HTNVP19tNvdbWgAZCoX2KgYjZsD9ZHc_hUi5NaAUg9JwrJVkfwI70MLpfNASLe5NUJoMV",
    "DJgiqtGZablrR6YA050qbni67VoqfjPReEMDIxhz8xbkyAnh6ugdAZK9DOSeCepZOgOi3jjfz2tg",
    "nhNkoWalH4ZGRb7HwS2_mxKAXmXpjMVt4FxIlrOfnjoivlunxqX018ma4WhDbSCGe3B45WIt2Afb",
    "9sppMbZe-F11r6Tq55NDUaPu6I5oNVjhnVP5-",
    "m_QfUqb8NHqU0fSW5XRZjQo_Kv7NffUT_McZKkT9Ctl1mxUlz4Y4iYyJiPeJ4oHS_hWqp1tAJk9D",
    "CRNhaqmHm1kwetjPK5b2xzhVcIuZyHFKCpSS0V69lQW4GCLnCZfLC22qv0HMpmd9l73R6-",
    "LJLmBLffDTSaYMiG0ImWCaFdzKhVlgiLcCvQWnwcx9ANWNMSoV-r6z4d6R-",
    "8HlS8xqDoFBGVL2BfUElEQ8vv4Za9jjGci6TFphE2apdTykehYvJmW3l0QrhQpERXOHIWHNEzkC6",
    "u17NkFmDsRgRgNsT5bSqtEPklGUnVy7IvNGCSi6bWHELaFUekZOiPStzBBbRVYB_E6k-",
    "IAm2tq6KAWhNsv56w5_E-dMbntdfzy0Lu0HLXwJRVh1cX-ntYuoGU-QYdiDYT86VLzaKFADovZYT",
    "EKvgcFVVZRlzkoSCdjNQZVLGCb3SWt44dbB5FIl90qqqxFYuDPe1TmjdplZ-",
    "6oQ7N6Bns6vMeYjjFy3zihdNQY1qduscHUyeNHQstgLQ2HUBPz8h8BJoS7U1Pbwpp0iUmIi9K5z0",
    "077IhnWwLk6Q8SDcwaRnlip1M0ovo_mbEULmwR-1RqkS3xJgbJZbsZn_UD-",
    "47q_yFDZ5JFJGAwh5TzX9BINLSR4CZ1SgEevZmx4hcQSAJoSUnPZfqbgDKWixusgRkN3tczdSjwZ",
    "Cl24gkNrF_cWJReheGms-mD5WGqOykeWgiEHtMPN1oJCq_vm8CnbEH7gco57WI5TCi1je9h0IPS7",
    "qXw2QaaXr0Aca8JU3s3d8wR4qpt56PRDcbGkfGEAvX2uRrNsod7JQ1eoeWgkQT9_8_4TPudE7YBA",
    "MNckY_i0P1yKsktMXmtxEPtvGLorREQK-2ubA8ocbKHwfdbj9yZTAXk-tqeVIeAotsEdoiJ4z8l1",
    "aDOR_EJjCdMzSlmGxGPqVElOKjfjW39QNhnHTVKWUlZ5PjurTsy0dlbnMg9Q-",
    "_KJ8u__tascdQvQKWC3Xyjxv3Y3tUKEwTJNEG4YIkP1CNKnVQEv8ZwFr7PtrBadwUMZ4wCyAkDAu",
    "6RGaJghoj76oCqSo7T_9yl0n1t-VYCgDWL8dWbkr3-",
    "Z_rOB55NfxAIsV55n843W_O6vwaVhpN9leBfVKQz5ofgP-TdaOM9sdIUoJLesXDO7VqC_1vI-vHZ",
    "wZu831TlnA8hdNO3PskC89DRklpyX_Pl1LacutnPFS3o-",
    "h9y19pV7KQmdqhOChV5T4tISew5CosaHh80oF-rnFSPwXakAwNq16ZZVxC5TR69Mwz9p57VU7F",
]

_CLIENT_PASSWORD_MODULUS_DATA = [
    "Sdw9AlmllSPMRstz4MGCBlxqyVo7_apogAlJDOX0GqamZo94_LYKUxMLJjTqQ7YVM-VJknzPX-TH",
    "LEl3MiuvzvUY6pfftM6_Nx24OofF5Jfjz3soezINHAsjJqkPq_3CKfioX8OCi9CUO9aF9Z8wXLfz",
    "Ap3_biASw9bkfpvwCiBnF5HgtPPOt_Kfsqz_EvtwTgWzbI9VPd4z7wC20z9CcoO0f42pSePo4HE0",
    "ezgIxSxXZlpjJL-PMhYAH6_uXYZYfqr_2wuZOsmoOpiTzkIIqJc1DhO5eDTzsOgJIc8pyq5XxV1T",
    "LKj6RlXMd5PYHOj2byqB3sCs_KFr6Q-",
    "QVQ7KYdkk7KJEH7f0FkgZu0CzolCtGYRpYe1oI9Lbts1JlT_u1V7F",
]



def _restore(parts: list[str]) -> str:
    encoded = "".join(parts)
    encoded = encoded[::-1]

    xored = base64.urlsafe_b64decode(encoded.encode("ascii"))

    compressed = bytes(
        b ^ _XOR_KEY[i % len(_XOR_KEY)]
        for i, b in enumerate(xored)
    )

    return zlib.decompress(compressed).decode("utf-8")


def get_client_signing_key() -> str:
    return _restore(_CLIENT_SIGNING_KEY_DATA)


def get_client_password_modulus() -> str:
    return _restore(_CLIENT_PASSWORD_MODULUS_DATA)