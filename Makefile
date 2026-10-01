PKG_DIR := packaging/arch

.PHONY: install uninstall test run clean po locale

install:    ## build the package and install it with pacman (also updates)
	cd $(PKG_DIR) && makepkg -sfci

uninstall:  ## remove the package
	sudo pacman -R msi-ultrapower

test:       ## run the unit tests
	PYTHONPATH=src:tests python3 -m unittest discover -s tests -v

run: locale  ## run the app from the source without installing (development)
	PYTHONPATH=src python3 -m msi_ultrapower.ui.app

LANGS := $(basename $(notdir $(wildcard po/*.po)))

po:         ## extract strings to po/msi-ultrapower.pot and update the translations
	xgettext --language=Python --from-code=UTF-8 --keyword=_ --keyword=N_ \
		--keyword=ngettext:1,2 --add-comments=Translators --package-name=msi-ultrapower \
		--output=po/msi-ultrapower.pot $$(find src -name '*.py' | sort)
	for lang in $(LANGS); do msgmerge --quiet --update --backup=none po/$$lang.po po/msi-ultrapower.pot; done

locale:     ## compile translations into build/locale (used by make run)
	for lang in $(LANGS); do \
		mkdir -p build/locale/$$lang/LC_MESSAGES; \
		msgfmt --check -o build/locale/$$lang/LC_MESSAGES/msi-ultrapower.mo po/$$lang.po; \
	done

clean:      ## remove build leftovers
	rm -rf $(PKG_DIR)/src $(PKG_DIR)/pkg $(PKG_DIR)/*.pkg.tar.* build
