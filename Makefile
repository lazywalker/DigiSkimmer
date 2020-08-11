APT="mirrors.ustc.edu.cn"
PLATFORM="linux/amd64,linux/arm64,linux/arm/v7"
VER=latest

all: base app

base:
	docker build --build-arg APT="${APT}" -t lazywalker/digiskr-base:${VER} -f docker/Dockerfile.base.${VER} .

app:
	docker build --build-arg VER=${VER} -t lazywalker/digiskr:${VER} -f docker/Dockerfile .

pushall: push
	docker push lazywalker/digiskr-base:${VER}

push:
	docker push lazywalker/digiskr:${VER}

buildx-base:
	docker buildx build  --build-arg APT="${APT}" --platform ${PLATFORM} -t lazywalker/digiskr-base:${VER} -f docker/Dockerfile.base.${VER} --push .

buildx:
	docker buildx build --build-arg VER=${VER} --platform ${PLATFORM} -t lazywalker/digiskr:${VER} -f docker/Dockerfile --push .