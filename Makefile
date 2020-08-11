.PHONY: help install pre-build build bump-patch bump-minor bump-major version bootstrap bootstrap-branch expand deploy clean deploy-spoke black pycodestyle
.DEFAULT_GOAL := help

WS=ignored/testing/$(ENV_NUMBER)
FACTORY_VENV=${WS}/factory
PUPPET_VENV=${WS}/puppet

include Makefile.CI
include Makefile.Project
include Makefile.Factory
include Makefile.CodeQuality
include Makefile.Test

help: help-prefix help-targets

help-prefix:
	@echo Usage:
	@echo '  make <target>'
	@echo '  make <VAR>=<value> <target>'
	@echo ''
	@echo Available targets

HELP_TARGET_MAX_CHAR_NUM = 25

help-targets:
	@awk '/^[a-zA-Z\-\_0-9]+:/ \
		{ \
			helpMessage = match(lastLine, /^## (.*)/); \
			if (helpMessage) { \
				helpCommand = substr($$1, 0, index($$1, ":")-1); \
				helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
				helpGroup = match(helpMessage, /^@([^ ]*)/); \
				if (helpGroup) { \
					helpGroup = substr(helpMessage, RSTART + 1, index(helpMessage, " ")-2); \
					helpMessage = substr(helpMessage, index(helpMessage, " ")+1); \
				} \
				printf "[ %s|  %-$(HELP_TARGET_MAX_CHAR_NUM)s %s\n", \
					helpGroup, helpCommand, helpMessage; \
			} \
		} \
		{ lastLine = $$0 }' \
		$(MAKEFILE_LIST) \
	| sort -t'|' -sk1,1 \
	| awk -F '|' ' \
			{ \
			cat = $$1; \
			if (cat != lastCat || lastCat == "") { \
				if ( cat == "0" ) { \
					print "Targets:" \
				} else { \
					gsub("_", " ", cat); \
					printf "%s ] \n", cat; \
				} \
			} \
			print " " $$2 \
		} \
		{ lastCat = $$1 }'
