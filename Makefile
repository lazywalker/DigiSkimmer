APT="mirrors.ustc.edu.cn"
PLATFORM="linux/amd64,linux/arm64,linux/arm/v7"

all: base app

app:
	docker build --rm -t lazywalker/digiskr -f docker/Dockerfile .

base:
	docker build --rm --build-arg APT="${APT}" -t lazywalker/digiskr-base -f docker/Dockerfile.base .

buildx:
	docker buildx build  --build-arg APT="${APT}" --platform ${PLATFORM} \
	 -t lazywalker/digiskr-base:latest -f docker/Dockerfile.base --push .
	docker buildx build  --build-arg APT="${APT}" --platform ${PLATFORM} \
	 -t lazywalker/digiskr:latest -f docker/Dockerfile --push .

pushall: push
	docker push lazywalker/digiskr-base:latest

push:
	docker push lazywalker/digiskr:latest
