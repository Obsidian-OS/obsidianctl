all: build

build:
	@cat ./modules/utils.py > obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/status.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/dualboot.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/install.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/switch.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/update.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/sync.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/enter.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/netupdate.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/diff.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/backup.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/health.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/obsiext.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./modules/migrations.py >> obsidianctl
	@printf "\n" >> obsidianctl
	@cat ./main >> obsidianctl
	@chmod +x obsidianctl
	@echo "--> obsidianctl"

clean:
	rm -f obsidianctl
install:
	install -Dm 755 -v obsidianctl /usr/local/sbin
uninstall:
	rm -f /usr/local/sbin/obsidianctl
