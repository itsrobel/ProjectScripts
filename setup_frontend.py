#!/usr/bin/env python3
import os
import subprocess
import sys


def create_file(base_path, filepath, content):
    full_path = os.path.join(base_path, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_frontend.py <app-name>")
        sys.exit(1)

    app_name = sys.argv[1]
    module_name = app_name.lower().replace(" ", "-")
    project_dir = f"{app_name}-frontend"

    # Create base directory
    os.makedirs(project_dir, exist_ok=True)

    # Create project structure
    subdirs = [
        "cmd/client",
        "internal/templates",
        "internal/client",
        "proto/api/v1",
        "static/css",
        "static/js/gen",
    ]

    for subdir in subdirs:
        os.makedirs(os.path.join(project_dir, subdir), exist_ok=True)

    # Change to project directory
    os.chdir(project_dir)

    # Initialize Go module
    subprocess.run(["go", "mod", "init", f"{module_name}-frontend"])

    # Initialize npm and install dependencies
    subprocess.run(["npm", "init", "-y"])
    subprocess.run(
        [
            "npm",
            "install",
            "@connectrpc/connect",
            "@connectrpc/connect-web",
            "@bufbuild/protobuf",
            "@bufbuild/buf",
        ]
    )

    # Install Go dependencies
    subprocess.run(["go", "mod", "tidy"])
    subprocess.run(
        ["go", "get", "github.com/a-h/templ", "github.com/bufbuild/connect-go"]
    )

    # Install templ
    subprocess.run(["go", "install", "github.com/a-h/templ/cmd/templ@latest"])

    files = {
        "proto/api/v1/service.proto": f"""syntax = "proto3";

package api.v1;
option go_package = "{module_name}-frontend/gen/api/v1;apiv1";

service GreetService {{
  rpc Greet(GreetRequest) returns (GreetResponse) {{}}
}}

message GreetRequest {{
  string name = 1;
}}

message GreetResponse {{
  string greeting = 1;
}}""",
        "buf.yaml": """version: v2
modules:
  - path: proto
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE""",
        "buf.gen.yaml": """version: v2
plugins:
  - remote: buf.build/bufbuild/connect-web
    opt: target=ts
    out: static/js/gen
  - remote: buf.build/bufbuild/es
    opt: target=ts
    out: static/js/gen""",
        "internal/templates/base.templ": f"""package templates

templ Base() {{
    <!DOCTYPE html>
    <html lang="en">
        <head>
            <meta charset="UTF-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <title>{app_name}</title>
            <script src="https://unpkg.com/@connectrpc/connect-web@v1.2.0/dist/umd/connect-web.js"></script>
            <script src="https://unpkg.com/@bufbuild/protobuf@v1.3.0/dist/umd/protobuf.js"></script>
            <script src="/static/js/gen/proto.js"></script>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100">
            <div class="container mx-auto px-4 py-8">
                {{ children... }}
            </div>
        </body>
    </html>
}}""",
        "internal/templates/index.templ": f"""package templates

templ Index() {{
    @Base() {{
        <div class="max-w-md mx-auto bg-white rounded-xl shadow-md overflow-hidden md:max-w-2xl p-6">
            <h1 class="text-2xl font-bold mb-4">{app_name}</h1>
            <div class="mb-4">
                <input 
                    type="text" 
                    id="nameInput" 
                    placeholder="Enter your name"
                    class="w-full px-3 py-2 border rounded-md"
                />
            </div>
            <button 
                onclick="sendGreeting()"
                class="bg-blue-500 text-white px-4 py-2 rounded-md hover:bg-blue-600"
            >
                Send Greeting
            </button>
            <div id="response" class="mt-4 text-gray-700"></div>
        </div>
        <script>
            const {{ createPromiseClient, createConnectTransport }} = window.ConnectWeb;

            const transport = createConnectTransport({{
                baseUrl: "http://localhost:8080",
                useBinaryFormat: true,
                interceptors: [],
            }});

            const client = createPromiseClient(window.Api.V1.GreetService, transport);

            async function sendGreeting() {{
                const name = document.getElementById('nameInput').value;
                try {{
                    const response = await client.greet({{
                        name: name
                    }});
                    document.getElementById('response').textContent = response.greeting;
                }} catch (error) {{
                    console.error('Error:', error);
                    document.getElementById('response').textContent = 'Error: ' + error.message;
                }}
            }}
        </script>
    }}
}}""",
        "cmd/client/main.go": f"""package main

import (
    "context"
    "log"
    "net/http"
    "{module_name}-frontend/internal/templates"
)

func main() {{
    mux := http.NewServeMux()

    mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir("static"))))

    mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {{
        if r.URL.Path != "/" {{
            http.NotFound(w, r)
            return
        }}
        templates.Index().Render(context.Background(), w)
    }})

    log.Println("Frontend server starting on :3000")
    if err := http.ListenAndServe(":3000", mux); err != nil {{
        log.Fatal(err)
    }}
}}""",
        "Makefile": """
.PHONY: build run templ generate-js

generate-js:
	npx buf generate proto --template buf.gen.yaml

templ:
	templ generate

build: templ generate-js
	go build -o bin/client cmd/client/main.go

run: templ generate-js
	go run cmd/client/main.go""",
        ".gitignore": """bin/
*_templ.go
node_modules/
static/js/gen/
package-lock.json""",
    }

    # Create all files
    for filepath, content in files.items():
        create_file(".", filepath, content)

    # Generate code
    subprocess.run(["npx", "buf", "generate", "proto", "--template", "buf.gen.yaml"])
    subprocess.run(["templ", "generate"])

    print("Frontend setup complete!")
    print("Run 'make run' to start the frontend server")


if __name__ == "__main__":
    main()

