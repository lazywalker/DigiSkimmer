
all: base app

app:
	docker build --rm -t lazywalker/digiskr -f docker/Dockerfile .

base:
	docker build --rm -t lazywalker/digiskr-base -f docker/Dockerfile.base .


pushall: push
	docker push lazywalker/digiskr-base:latest

push:
	docker push lazywalker/digiskr:latest