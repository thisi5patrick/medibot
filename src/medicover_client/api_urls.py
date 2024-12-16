SCHEMA = "https://"

AUTH_BASE_URL = SCHEMA + "login-online24.medicover.pl"
AUTHORIZATION_URL = AUTH_BASE_URL + "/connect/authorize"
TOKEN_URL = AUTH_BASE_URL + "/connect/token"

API_BASE_URL = SCHEMA + "online24.medicover.pl"
OIDC_URL = API_BASE_URL + "/signin-oidc"

HOST = "api-gateway-online24.medicover.pl"
BASE_URL = SCHEMA + HOST

FILTER_SEARCH_URL = BASE_URL + "/appointments/api/search-appointments/filters"
APPOINTMENT_SEARCH_URL = BASE_URL + "/appointments/api/person-appointments/appointments"
REGION_SEARCH_URL = BASE_URL + "/service-selector-configurator/api/search-appointments/filters/initial-filters"
AVAILABLE_SLOT_SEARCH_URL = BASE_URL + "/appointments/api/search-appointments/slots"
