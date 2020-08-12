APT="mirrors.ustc.edu.cn"
PLATFORM="linux/amd64,linux/arm64,linux/arm/v7"
TAG=buster

all: base app

base:
	docker build --build-arg APT="${APT}" -t lazywalker/digiskr-base -f docker/Dockerfile.base.${TAG} .

app:
	docker build -t lazywalker/digiskr -f docker/Dockerfile .

pushall: push
	docker push lazywalker/digiskr-base

push:
	docker push lazywalker/digiskr

buildx-base:
	docker buildx build  --build-arg APT="${APT}" --platform ${PLATFORM} -t lazywalker/digiskr-base -f docker/Dockerfile.base.${TAG} --push .

buildx:
	docker buildx build --platform ${PLATFORM} -t lazywalker/digiskr -f docker/Dockerfile --push .