.PHONY: install uninstall clean

PREFIX ?= /usr/local/bin
VENV_DIR := $(CURDIR)/.venv

install: $(VENV_DIR)
	@echo ""
	@echo "  Installed. Run with:"
	@echo "    $(CURDIR)/sonogram <file.wav>"
	@echo ""
	@echo "  Or symlink to PATH:"
	@echo "    sudo ln -sf $(CURDIR)/sonogram $(PREFIX)/sonogram"
	@echo ""

$(VENV_DIR): requirements.txt
	@echo "Creating Python environment..."
	@python3 -m venv $(VENV_DIR)
	@$(VENV_DIR)/bin/pip install --quiet --upgrade pip
	@$(VENV_DIR)/bin/pip install --quiet -r requirements.txt
	@touch $(VENV_DIR)

uninstall:
	rm -f $(PREFIX)/sonogram

clean:
	rm -rf $(VENV_DIR)
