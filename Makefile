.PHONY: translate

translate:
	msgfmt src/locales/pl/LC_MESSAGES/messages.po -o src/locales/pl/LC_MESSAGES/messages.mo
	msgfmt src/locales/en/LC_MESSAGES/messages.po -o src/locales/en/LC_MESSAGES/messages.mo
