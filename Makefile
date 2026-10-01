PKG_DIR := packaging/arch

.PHONY: install uninstall test run clean po locale

install:    ## paketi derle ve pacman ile kur (güncellemek için de aynı komut)
	cd $(PKG_DIR) && makepkg -sfci

uninstall:  ## paketi kaldır
	sudo pacman -R msi-ultrapower

test:       ## birim testlerini çalıştır
	PYTHONPATH=src:tests python3 -m unittest discover -s tests -v

run: locale  ## arayüzü kurmadan doğrudan kaynak koddan çalıştır (geliştirme için)
	PYTHONPATH=src python3 -m msi_ultrapower.ui.app

LANGS := $(basename $(notdir $(wildcard po/*.po)))

po:         ## kaynak metinleri po/msi-ultrapower.pot'a çıkar ve çevirileri güncelle
	xgettext --language=Python --from-code=UTF-8 --keyword=_ --keyword=N_ \
		--keyword=ngettext:1,2 --add-comments=Translators --package-name=msi-ultrapower \
		--output=po/msi-ultrapower.pot $$(find src -name '*.py' | sort)
	for lang in $(LANGS); do msgmerge --quiet --update --backup=none po/$$lang.po po/msi-ultrapower.pot; done

locale:     ## çevirileri build/locale'e derle (make run bunları kullanır)
	for lang in $(LANGS); do \
		mkdir -p build/locale/$$lang/LC_MESSAGES; \
		msgfmt --check -o build/locale/$$lang/LC_MESSAGES/msi-ultrapower.mo po/$$lang.po; \
	done

clean:      ## paket derleme artıklarını sil
	rm -rf $(PKG_DIR)/src $(PKG_DIR)/pkg $(PKG_DIR)/*.pkg.tar.* build
