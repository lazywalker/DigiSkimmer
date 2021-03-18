APT="mirrors.ustc.edu.cn"
PLATFORM="linux/amd64,linux/arm64,linux/arm/v7"
TAG=alpine
VER=0.32
# VER=latest
VER_BASE=wsjtx-2.2.2


all: base app

base:
	docker build --build-arg APT="${APT}" -t lazywalker/digiskr-base:${VER_BASE} -f docker/Dockerfile.base.${TAG} .

app:
	docker build -t lazywalker/digiskr -f docker/Dockerfile .

pushall: push
	docker push lazywalker/digiskr-base:${VER_BASE}

push:
	docker push lazywalker/digiskr:${VER}

buildx: buildx-base buildx-app

buildx-base:
	docker buildx build  --build-arg APT="${APT}" --platform ${PLATFORM} -t lazywalker/digiskr-base:${VER_BASE} -f docker/Dockerfile.base.${TAG} --push .

buildx-app:
	docker buildx build --platform ${PLATFORM} -t lazywalker/digiskr:${VER} -f docker/Dockerfile --push .