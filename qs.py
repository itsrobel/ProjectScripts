import argparse
import os
import subprocess
from typing import Optional


def create_shared_structure(name: str):
    # Create main project directory
    os.makedirs(f"{name}/internal/handlers", exist_ok=True)
    os.makedirs(f"{name}/protos/apiv1", exist_ok=True)
    os.makedirs(f"{name}/bin", exist_ok=True)

    os.chdir(name)
    os.system(f"go mod init {name}")
    os.system("git init --initial-branch=main")

    os.system("go mod tidy")


def setup_build(name: str):
    with open("buf.yaml", "w") as f:
        f.write("""
# For details on buf.yaml configuration, visit https://buf.build/docs/configuration/v2/buf-yaml
version: v2
modules:
  - path: protos
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
    """)
    with open(".gitignore", "w") as f:
        f.write("""
*.db
bin/
node_modules/
public/css/main.css
*/templates/*_templ.go
    """)
    with open("buf.gen.yaml", "w") as f:
        f.write("""
version: v2
clean: true
managed:
  enabled: true
plugins:
  - remote: buf.build/connectrpc/go
    out: internal/services
    opt:
      - paths=source_relative
  - remote: buf.build/protocolbuffers/go
    out: internal/services
    opt:
      - paths=source_relative

inputs:
  - directory: protos
    """)

    with open("Taskfile.yaml", "w") as f:
        f.write(f"""
version: "3"

tasks:
  dev-client:
    cmds:
      - bunx tailwindcss -i ./assets/css/app.css -o ./public/css/main.css
      - templ generate
      - buf generate
      - go run cmd/client/main.go
  dev-server:
    cmds:
      - buf generate
      - go run cmd/server/main.go
  build:
    cmds:
      - bunx tailwindcss -i ./assets/css/app.css -o ./public/css/main.css
      - templ generate
      - go build -o ./bin/server cmd/server/main.go
      - go build -o ./bin/client cmd/client/main.go

    desc: "Build the Go project"
  docker-build:
    cmds:
      - docker build -t {name} .
  docker-run:
    cmds:
      - docker run -d -p 80:8080 --name {name}_container {name} 
  lint:
    cmds:
      - golangci-lint run
    desc: "Lint the code"

  clean:
    cmds:
      - rm -rf myapp
    desc: "Clean the build artifacts"


  """)


def setup_internal_shared(name: str):
    with open("protos/apiv1/service.proto", "w") as f:
        f.write(f"""
syntax = "proto3";

package apiv1;
option go_package = "{name}/internal/services/apiv1";

service GreetService {{
rpc Greet(GreetRequest) returns (GreetResponse) {{}}
}}

message GreetRequest {{
string name = 1;
}}

message GreetResponse {{
string greeting = 1;
}}
    """)


def setup_server(name: str):
    # Initialize Go module
    os.makedirs("cmd/server", exist_ok=True)
    # Install backend dependencies
    os.system("go get connectrpc.com/connect golang.org/x/net/http2 github.com/rs/cors")
    os.system("go install github.com/bufbuild/buf/cmd/buf@latest")

    # Create backend-specific files
    with open("cmd/server/main.go", "w") as f:
        f.write(f"""
package main

import (
    "log"
    "net/http"
    "{name}/internal/services/apiv1/apiv1connect"
    "{name}/internal/handlers"
    "github.com/rs/cors"
)

func main() {{
    mux := http.NewServeMux()
    
    // Initialize gRPC handler 
    greetServer := handlers.NewGreetServer()
    path, handler := apiv1connect.NewGreetServiceHandler(greetServer)
    mux.Handle(path, handler)
    
    // Configure CORS
    corsHandler := cors.New(cors.Options{{
        AllowedOrigins: []string{{"*"}},
        AllowedMethods: []string{{"GET", "POST", "OPTIONS"}},
        AllowedHeaders: []string{{"Accept", "Content-Type", "Connect-Protocol-Version"}},
    }})

    wrappedHandler := corsHandler.Handler(mux)
    
    log.Println("Server starting on :8080")
    if err := http.ListenAndServe(":8080", wrappedHandler); err != nil {{
        log.Fatal(err)
    }}
}}
    """)
    with open("internal/handlers/greetServer.go", "w") as f:
        f.write(f"""
package handlers

import (
    "context"
    "fmt"
    apiv1 "{name}/internal/services/apiv1"
    "connectrpc.com/connect"
)

type GreetServer struct{{}}

func NewGreetServer() *GreetServer {{
    return &GreetServer{{}}
}}

func (s *GreetServer) Greet(
    ctx context.Context,
    req *connect.Request[apiv1.GreetRequest],
) (*connect.Response[apiv1.GreetResponse], error) {{
    response := connect.NewResponse(&apiv1.GreetResponse{{
        Greeting: fmt.Sprintf("Hello, %s!", req.Msg.Name),
    }})
    return response, nil
}}
    """)


def setup_client(name: str):
    os.makedirs("cmd/client", exist_ok=True)
    os.makedirs("internal/templates", exist_ok=True)
    os.makedirs("assets/css", exist_ok=True)
    os.makedirs("public/css", exist_ok=True)

    # Install frontend dependencies
    os.system("go get github.com/a-h/templ")
    os.system("go install github.com/a-h/templ/cmd/templ@latest")

    # Create frontend-specific files
    setup_client_templates()
    setup_client_js(name)
    with open("cmd/client/main.go", "w") as f:
        f.write(f"""
package main

import (
    "log"
    "net/http"
    "{name}/internal/services/apiv1/apiv1connect"
    "{name}/internal/handlers"
    "github.com/rs/cors"
)

func main() {{
    mux := http.NewServeMux()
    
    
    // Initialize HTTP client for internal gRPC calls
    client := apiv1connect.NewGreetServiceClient(
        http.DefaultClient,
        "http://localhost:8080",
    )
    
    // Initialize handlers
    greetClientHandlers := handlers.NewGreetClient(client)
    
    // Routes
    mux.HandleFunc("/", greetClientHandlers.Index)
    mux.HandleFunc("/greet", greetClientHandlers.HandleGreet)
    
    // Serve static files
    fs := http.FileServer(http.Dir("public"))
    mux.Handle("/public/", http.StripPrefix("/public/", fs))
    
    // Configure CORS
    corsHandler := cors.New(cors.Options{{
        AllowedOrigins: []string{{"*"}},
        AllowedMethods: []string{{"GET", "POST", "OPTIONS"}},
        AllowedHeaders: []string{{"Accept", "Content-Type", "Connect-Protocol-Version"}},
    }})

    wrappedHandler := corsHandler.Handler(mux)
    
    log.Println("Server starting on :3000")
    if err := http.ListenAndServe(":3000", wrappedHandler); err != nil {{
        log.Fatal(err)
    }}
}}
""")

        # Write frontend server implementation
        pass

    with open("internal/handlers/greetClient.go", "w") as f:
        f.write(f"""
package handlers 

import (
    "context"
    "net/http"
    "{name}/internal/services/apiv1"
    "{name}/internal/services/apiv1/apiv1connect"
    "{name}/internal/templates"
    "connectrpc.com/connect"
)

type GreetClient struct {{
    greetClient apiv1connect.GreetServiceClient
}}

func NewGreetClient(greetClient apiv1connect.GreetServiceClient) *GreetClient {{
    return &GreetClient{{
        greetClient: greetClient,
    }}
}}

func (h *GreetClient) Index(w http.ResponseWriter, r *http.Request) {{
    component := templates.Index()
    component.Render(context.Background(), w)
}}

func (h *GreetClient) HandleGreet(w http.ResponseWriter, r *http.Request) {{
    if err := r.ParseForm(); err != nil {{
        http.Error(w, "Failed to parse form", http.StatusBadRequest)
        return
    }}

    name := r.FormValue("name")
    req := connect.NewRequest(&apiv1.GreetRequest{{Name: name}})
    
    resp, err := h.greetClient.Greet(r.Context(), req)
    if err != nil {{
        http.Error(w, "Failed to greet", http.StatusInternalServerError)
        return
    }}

    component := templates.GreetingResponse(resp.Msg.Greeting)
    component.Render(r.Context(), w)
}}
""")


def setup_client_js(name: str):
    # TODO: setup the bun env
    os.system("bun init")
    os.system("bun i tailwindcss @tailwindcss/cli daisyui@beta")
    with open("tailwind.config.js", "w") as f:
        f.write("""
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./internal/templates/**/*.templ"],
  plugins: [require("@tailwindcss/typography")],
  theme: {
    fontFamily: {
      excali: ["Excalifont", "sans-serif"],
      mono: ["SFMono-Regular", "jetbrains mono", "monospace"],
    },
  },
};
        """)
    with open("assets/css/app.css", "w") as f:
        f.write("""
@import "tailwindcss";

@plugin "daisyui" {
  themes: nord --default;
}
""")


def setup_client_templates():
    with open("internal/templates/layout.templ", "w") as f:
        f.write("""
package templates

templ Layout(title string) {
    <!DOCTYPE html>
    <html lang="en" data-theme="wireframe">
        <head>
            <meta charset="UTF-8"/>
            <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
            <title>{ title }</title>
            <script src="https://unpkg.com/htmx.org@1.9.6"></script>
            <link href="/public/css/main.css" rel="stylesheet"/>
        </head>
        <body class="min-h-screen bg-base-100">
            <main class="container mx-auto px-4 py-8">
                { children... }
            </main>
        </body>
    </html>
}
""")

    with open("internal/templates/index.templ", "w") as f:
        f.write("""
package templates

templ Index() {
    @Layout("Home") {
        <div class="max-w-md mx-auto">
            <form class="space-y-4" hx-post="/greet" hx-target="#greeting" hx-swap="innerHTML">
                <div class="form-control">
                    <label class="label">
                        <span class="label-text">Name</span>
                    </label>
                    <input type="text" name="name" class="input input-bordered" required/>
                </div>
                <button type="submit" class="btn btn-primary w-full">
                    Greet
                </button>
            </form>
            <div id="greeting" class="mt-4 text-center"></div>
        </div>
    }
}

templ GreetingResponse(greeting string) {
    <div class="alert alert-success">
        <span>{ greeting }</span>
    </div>
}
""")

    os.system("templ generate")


def create_project(name: str, project_type: str):
    module_name = name.lower().replace(" ", "-")

    create_shared_structure(module_name)

    setup_build(module_name)
    setup_internal_shared(module_name)

    if project_type in ["backend", "both"]:
        setup_server(module_name)

    if project_type in ["frontend", "both"]:
        setup_client(module_name)

    os.system("buf generate")


def main():
    parser = argparse.ArgumentParser(description="Generate unified project structure")
    parser.add_argument("name", help="Name of the project")
    parser.add_argument(
        "--type",
        choices=["frontend", "backend", "both"],
        default="both",
        help="Type of project to generate",
    )

    args = parser.parse_args()
    create_project(args.name, args.type)


if __name__ == "__main__":
    main()
