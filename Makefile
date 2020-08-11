APT="mirrors.ustc.edu.cn"
PLATFORM="linux/amd64,linux/arm64,linux/arm/v7"
TAG=latest

all: base app

base:
	docker build --build-arg APT="${APT}" -t lazywalker/digiskr-base:${TAG} -f docker/Dockerfile.base.${TAG} .

app:
	docker build --build-arg TAG=${TAG} -t lazywalker/digiskr:${TAG} -f docker/Dockerfile .

pushall: push
	docker push lazywalker/digiskr-base:${TAG}

push:
	docker push lazywalker/digiskr:${TAG}

buildx-base:
	docker buildx build  --build-arg APT="${APT}" --platform ${PLATFORM} -t lazywalker/digiskr-base:${TAG} -f docker/Dockerfile.base.${TAG} --push .

buildx:
	docker buildx build --build-arg TAG=${TAG} --platform ${PLATFORM} -t lazywalker/digiskr:${TAG} -f docker/Dockerfile --push .