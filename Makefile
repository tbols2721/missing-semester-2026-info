MANUAL := missing-semester-2026
PREFIX ?= $(HOME)/.local
INFODIR ?= $(PREFIX)/share/info
SCRIPT_DIR ?= $(CURDIR)/scripts
PYTHON ?= python3

.PHONY: all check selftest tools regenerate check-links install

all: info/$(MANUAL).info info/dir

info/$(MANUAL).info: manual/$(MANUAL).texi
	mkdir -p info
	makeinfo --no-split --fill-column=79 -o $@ $<

info/dir: info/$(MANUAL).info
	install-info --info-dir=info $<

# Maintenance tools are ordinary source files in this checkout.
tools:
	test -f "$(SCRIPT_DIR)/missing_semester_info.py"
	test -f "$(SCRIPT_DIR)/missing_semester_links.py"

check: all tools
	$(PYTHON) "$(SCRIPT_DIR)/missing_semester_info.py" verify --root "$(CURDIR)"

selftest: all tools
	$(PYTHON) "$(SCRIPT_DIR)/missing_semester_info.py" selftest --root "$(CURDIR)"

regenerate: tools
	$(PYTHON) "$(SCRIPT_DIR)/missing_semester_info.py" build --root "$(CURDIR)"

check-links: tools
	$(PYTHON) "$(SCRIPT_DIR)/missing_semester_links.py" --root "$(CURDIR)"

install: all
	install -d "$(DESTDIR)$(INFODIR)"
	install -m 644 info/$(MANUAL).info "$(DESTDIR)$(INFODIR)/$(MANUAL).info"
	install-info --info-dir="$(DESTDIR)$(INFODIR)" "$(DESTDIR)$(INFODIR)/$(MANUAL).info"
