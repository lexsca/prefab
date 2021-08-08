.PHONY: app run clean

IMAGE_REPO ?= quay.io/lexsca/example

app:
	docker run --rm -v `pwd`:/build -w /build \
		-v /var/run/docker.sock:/var/run/docker.sock \
		--platform linux/amd64 quay.io/lexsca/prefab:dood \
		--repo ${IMAGE_REPO} --target app:app 

run:
	docker run --platform linux/amd64 -it --rm -p 8000:8000 ${IMAGE_REPO}:app

clean: IMAGES = $(shell docker images \
	--format '{{.Repository}}:{{.Tag}}' ${IMAGE_REPO})
clean:
	$(foreach image,$(IMAGES),docker rmi $(image);)
	docker image prune -f
