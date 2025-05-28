from automation import email_account, social_media
from enum import Enum

MAIL_BANK_TYPES = {
    0: ("Google", email_account.Google),
    #1: ("Onet", email_account.OnetBank),
    #2: ("Proton", email_account.ProtonBank),
    #3: ("Tutanota", email_account.TutanotaBank)
}

SOCIAL_MEDIA_BANK_TYPES = {
    0: ("TikTok", social_media.TikTok),
    #1: ("Instagram", social_media.Instagr),
    #2: ("X (dawniej Twitter)", emailBankBase.XBank),
    #3: ("YouTube", emailBankBase.YouTubeBank)
}

class AccountType(Enum):
    ADMIN = "admins"
    WORKER = "workers"
    UNAUTHORIZED = "unauthorized"