import os
import sys

# Check if application name is provided
if len(sys.argv) < 2:
    print("Usage: python setup_frontend.py <app-name>")
    sys.exit(1)

APP_NAME = sys.argv[1]
MODULE_NAME = APP_NAME.lower().replace(" ", "-")

# Create project structure
os.makedirs(f"{APP_NAME}-frontend/cmd/server", exist_ok=True)
os.makedirs(f"{APP_NAME}-frontend/internal/service", exist_ok=True)
os.makedirs(f"{APP_NAME}-frontend/internal/templates", exist_ok=True)
os.makedirs(f"{APP_NAME}-frontend/proto/apiv1", exist_ok=True)
os.makedirs(f"{APP_NAME}-frontend/gen", exist_ok=True)
os.makedirs(f"{APP_NAME}-frontend/assets/css", exist_ok=True)

os.chdir(f"{APP_NAME}-frontend")

# Initialize Go module
os.system(f"go mod init {MODULE_NAME}-frontend")

# Install dependencies
os.system("go mod tidy")
os.system(
    "go get connectrpc.com/connect golang.org/x/net/http2 github.com/rs/cors github.com/a-h/templ"
)
os.system("go install github.com/bufbuild/buf/cmd/buf@latest")
os.system("go install github.com/a-h/templ/cmd/templ@latest")

# Create base layout template
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
            <link href="/assets/css/main.css" rel="stylesheet"/>
        </head>
        <body class="min-h-screen bg-base-100">
            <main class="container mx-auto px-4 py-8">
                { children... }
            </main>
        </body>
    </html>
}
""")

# Create index template
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

# Create main.css for Tailwind
with open("assets/css/main.css", "w") as f:
    f.write("""
@tailwind base;
@tailwind components;
@tailwind utilities;
""")

# Create handlers.go
with open("internal/service/handlers.go", "w") as f:
    f.write(f"""
package service

import (
    "context"
    "net/http"
    "{MODULE_NAME}-frontend/internal/services/apiv1"
    "{MODULE_NAME}-frontend/internal/services/apiv1/apiv1connect"
    "{MODULE_NAME}-frontend/internal/templates"
    "connectrpc.com/connect"
)

type Handlers struct {{
    greetClient apiv1connect.GreetServiceClient
}}

func NewHandlers(greetClient apiv1connect.GreetServiceClient) *Handlers {{
    return &Handlers{{
        greetClient: greetClient,
    }}
}}

func (h *Handlers) Index(w http.ResponseWriter, r *http.Request) {{
    component := templates.Index()
    component.Render(context.Background(), w)
}}

func (h *Handlers) HandleGreet(w http.ResponseWriter, r *http.Request) {{
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

# Update server implementation
with open("cmd/server/main.go", "w") as f:
    f.write(f"""
package main

import (
    "log"
    "net/http"
    "{MODULE_NAME}-frontend/internal/services/apiv1/apiv1connect"
    "{MODULE_NAME}-frontend/internal/service"
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
    handlers := service.NewHandlers(client)
    
    // Routes
    mux.HandleFunc("/", handlers.Index)
    mux.HandleFunc("/greet", handlers.HandleGreet)
    
    // Serve static files
    fs := http.FileServer(http.Dir("assets"))
    mux.Handle("/assets/", http.StripPrefix("/assets/", fs))
    
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

# Update Makefile
# with open("Makefile", "w") as f:
#     f.write("""
# .PHONY: generate build run setup-frontend dev
#
# generate:
# 	buf generate
# 	templ generate
#
# build: generate
# 	go build -o bin/server cmd/server/main.go
#
# run: generate
# 	go run cmd/server/main.go
#
# setup-frontend:
# 	bun install
#
# dev:
# 	bun run dev
#
# watch:
# 	templ generate --watch
# """)

with open("Taskfile.yaml", "w") as f:
    f.write(f"""

version: "3"

tasks:
  dev:
    cmds:
      - bun run build
      - templ generate
      - go run cmd/server/main.go
  build:
    cmds:
      - bun run build
      - templ generate
      - go build -o ./bin/app cmd/server/main.go

    desc: "Build the Go project"
  #TODO: Make tests later
  # test:
  #   cmds:
  #     - go test ./...
  #   desc: "Run tests"

  docker-build:
    cmds:
      - docker build -t {MODULE_NAME} .
  docker-run:
    cmds:
      - docker run -d -p 80:8080 --name {MODULE_NAME}_frontend_container {MODULE_NAME} 
  lint:
    cmds:
      - golangci-lint run
    desc: "Lint the code"

  clean:
    cmds:
      - rm -rf myapp
    desc: "Clean the build artifacts"


  """)

with open("proto/apiv1/service.proto", "w") as f:
    f.write(f"""
syntax = "proto3";

package apiv1;
option go_package = "{MODULE_NAME}-frontend/internal/services/apiv1";

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

# Create buf.yaml
with open("buf.yaml", "w") as f:
    f.write("""
version: v2
modules:
  - path: proto
lint:
  use:
    - STANDARD
breaking:
  use:
    - FILE
""")

# Create buf.gen.yaml
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
""")

# Create service implementation
# with open("internal/service/greet.go", "w") as f:
#     f.write(f"""
# package service
#
# import (
#     "context"
#     "fmt"
#     apiv1 "{MODULE_NAME}-frontend/internal/services/apiv1"
#     "connectrpc.com/connect"
# )
#
# type GreetServer struct{{}}
#
# func NewGreetServer() *GreetServer {{
#     return &GreetServer{{}}
# }}
#
# func (s *GreetServer) Greet(
#     ctx context.Context,
#     req *connect.Request[apiv1.GreetRequest],
# ) (*connect.Response[apiv1.GreetResponse], error) {{
#     response := connect.NewResponse(&apiv1.GreetResponse{{
#         Greeting: fmt.Sprintf("Hello, %s!", req.Msg.Name),
#     }})
#     return response, nil
# }}
# """)


# Create tailwind.config.js
with open("tailwind.config.js", "w") as f:
    f.write("""
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./internal/templates/**/*.templ"],
  plugins: [require("@tailwindcss/typography"), require("daisyui")],
  theme: {
    fontFamily: {
      'excali': ["Excalifont", "sans-serif"],
      'mono': ["SFMono-Regular", 'jetbrains mono', "monospace"],
    },
  },
  daisyui: {
    themes: ["wireframe", "dim"],
    base: true,
    styled: true,
    utils: true,
    prefix: "",
    themeRoot: ":root",
  },
  darkMode: ["selector", '[data-theme="dim"]'],
};
""")

# Create package.json
with open("package.json", "w") as f:
    f.write("""
{
  "name": "app",
  "module": "index.ts",
  "type": "module",
  "scripts": {
    "dev": "bunx tailwindcss -i ./assets/css/main.css -o ./assets/css/main.css --watch",
    "build": "bunx tailwindcss -i ./assets/css/main.css -o ./assets/css/main.css --minify"
  },
  "devDependencies": {
    "@tailwindcss/typography": "^0.5.10",
    "bun-types": "latest",
    "daisyui": "^4.4.19",
    "tailwindcss": "^3.3.6"
  }
}
""")

# Create gitignore
with open(".gitignore", "w") as f:
    f.write("""
bin/
gen/
node_modules/
**/*_templ.go
""")

# Generate code
os.system("buf generate")

print("frontend setup complete!")
print("To start development:")
print("1. Run 'make setup-frontend' to install frontend dependencies")
print("2. Run 'make watch' in one terminal to watch templ files")
print("3. Run 'make dev' in another terminal to watch CSS files")
print("4. Run 'make run' to start the server")
