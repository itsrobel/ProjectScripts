
.PHONY: generate build run setup-frontend dev

generate:
	buf generate
	templ generate

build: generate
	go build -o bin/server cmd/server/main.go

run: generate
	go run cmd/server/main.go

setup-frontend:
	bun install

dev:
	bun run dev

watch:
	templ generate --watch
