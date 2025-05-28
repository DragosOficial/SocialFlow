from enum import Enum

class TaskType(Enum):
    CHECK_FOR_UPDATES = "CHECK_FOR_UPDATES"
    TT_COPY_ACCOUNT_DATA = "TT_COPY_ACCOUNT_DATA"
    TT_MASS_REPORT = "TT_MASS_REPORT"
    G_GENERATE_ACCOUNT = "G_GENERATE_ACCOUNT"

class ReportTypeMain(Enum):
    PRZEMOC = "Przemoc, nadużycia i wykorzystywanie w celach przestępczych"
    NIENAWISC = "Nienawiść i prześladowanie"
    SAMOBOJSTWO = "Samobójstwo i samookaleczanie"
    ZABURZONE = "Zaburzone odżywianie i niezdrowy obraz ciała"
    NIEBEZPIECZNE = "Niebezpieczne działania i wyzwania"
    NAGOSC = "Nagość i treści seksualne"

class ReportTypeSubPrzemoc(Enum):
    POD18 = "Wykorzystywanie i znęcanie się nad osobami poniżej 18 roku życia"
    FIZYCZNA = "Przemoc fizyczna i brutalne groźby"
    SEKSUALNE = "Wykorzystanie seksualne i nadużycia"
    LUDZIE = "Wykorzystywanie ludzi"
    ZWIERZETA = "Znęcanie się nad zwierzętami"
    INNA = "Inna działalność przestępcza"

class ReportTypeSubNienawisc(Enum):
    NIENAWISC = "Mowa nienawiści i nienawistne zachowania"

class ReportTypeSubNagosc(Enum):
    MLodziez_SEX = "Aktywność seksualna młodzieży, nagabywanie i wykorzystywanie seksualne"
    MLodziez_ZACH = "Zachowania seksualne młodzieży"
    DOROSLI = "Aktywność i usługi seksualne osób dorosłych oraz nagabywanie"
    DOROSLI_NAGOSC = "Nagość dla dorosłych"
    JAZYK = "Język o wyraźnym zabarwieniu seksualnym"