PKG_DIR := packaging/arch

.PHONY: install uninstall test run clean

install:    ## paketi derle ve pacman ile kur (güncellemek için de aynı komut)
	cd $(PKG_DIR) && makepkg -sfci

uninstall:  ## paketi kaldır
	sudo pacman -R pil-modu

test:       ## birim testlerini çalıştır
	PYTHONPATH=src:tests python3 -m unittest discover -s tests -v

run:        ## arayüzü kurmadan doğrudan kaynak koddan çalıştır (geliştirme için)
	PYTHONPATH=src python3 -m pil_modu.ui.app

clean:      ## paket derleme artıklarını sil
	rm -rf $(PKG_DIR)/src $(PKG_DIR)/pkg $(PKG_DIR)/*.pkg.tar.*
