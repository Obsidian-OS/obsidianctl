all: build

build:
	echo -e "#!/usr/bin/env python3\nimport argparse" > obsidianctl
	cat ./modules/utils.py >> obsidianctl
	echo -e "\n" >> obsidianctl
	cat ./modules/status.py >> obsidianctl
	echo -e "\n" >> obsidianctl
	cat ./modules/install.py >> obsidianctl
	echo -e "\n" >> obsidianctl
	cat ./modules/switch.py >> obsidianctl
	echo -e "\n" >> obsidianctl
	cat ./modules/update.py >> obsidianctl
	echo -e "\n" >> obsidianctl
	cat ./main >> obsidianctl
	chmod +x obsidianctl

clean:
	rm -f obsidianctl
install:
	install -Dm 755 -v obsidianctl /usr/local/sbin
uninstall:
	rm -f /usr/local/sbin/obsidianctl
