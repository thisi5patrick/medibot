BASE_HOST = "mol.medicover.pl"
BASE_URL = "https://" + BASE_HOST

BASE_OAUTH_URL = "https://oauth.medicover.pl"

APPOINTMENTS = BASE_URL + "/api/MyVisits/SearchVisitsToView"
REGIONS = BASE_URL + "/api/MyVisits/SearchFreeSlotsToBook/GetInitialFiltersData"
FILTERS = BASE_URL + "/api/MyVisits/SearchFreeSlotsToBook/GetFiltersData"
AVAILABLE_SLOTS = BASE_URL + "/api/MyVisits/SearchFreeSlotsToBook"
