PWD=$(shell pwd)
include ../config.mk

all: uninstall | install

install:
	for a in `find * -maxdepth 0 -type d` ; do \
		for b in ${SKILLDIRS} ; do \
			ln -fs $(PWD)/$$a $$b/$$a ; \
		done ; \
	done

uninstall:
	for a in `find * -maxdepth 0 -type d` ; do \
		for b in ${SKILLDIRS} ; do \
			rm -f $$b/$$a ; \
		done ; \
	done

.PHONY: all install uninstall
