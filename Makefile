
all:base app

app:
	docker build --rm -t lazywalker/digiskr -f docker/Dockerfile .

base:
	docker build --rm -t lazywalker/digiskr-base -f docker/Dockerfile.base .