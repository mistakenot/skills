.PHONY: compile lint check

compile:
	python src/compile.py

lint:
	autoskill lint

check: compile lint
