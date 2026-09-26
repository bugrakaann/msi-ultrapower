.PHONY: install uninstall test run

install:    ## ~/.local/bin başlatıcılarını ve menü girdisini kur
	./scripts/install.sh

uninstall:  ## başlatıcıları kaldır
	./scripts/uninstall.sh

test:       ## birim testlerini çalıştır
	PYTHONPATH=src:tests python3 -m unittest discover -s tests -v

run:        ## arayüzü kurmadan doğrudan buradan çalıştır
	PYTHONPATH=src python3 -m pil_modu.ui.app
