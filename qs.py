import argparse
import os


def create_shared_structure(name: str, git: bool):
    # Create main project directory
    os.makedirs(f"{name}/internal/handlers", exist_ok=True)
    os.makedirs(f"{name}/protos/apiv1", exist_ok=True)
    bin_path = os.path.abspath(f"{name}/bin")  # Absolute path required
    os.environ["GOBIN"] = bin_path
    os.makedirs(bin_path, exist_ok=True)

    os.chdir(name)
    os.system(f"go mod init {(f'github.com/itsrobel/{name}' if git else name)}")
    if git:
        os.system("git init --initial-branch=main")


def setup_build(module_name: str, module_path: str):
    with open("protos/apiv1/service.proto", "w") as f:
        f.write(f"""
syntax = "proto3";

package apiv1;
option go_package = "{module_path}/internal/services/apiv1";

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
  - local: ./bin/protoc-gen-go
    out: internal/services
    opt:
      - paths=source_relative
  - local: ./bin/protoc-gen-connect-go
    out: internal/services
    opt:
      - paths=source_relative

inputs:
  - directory: protos
    """)

    with open("air-server.toml", "w") as f:
        f.write("""
[build]
cmd = "./bin/buf generate && go build -o ./tmp/server cmd/server/main.go"
bin = "./tmp/server"
include_ext = ["go", "templ", "proto"]
exclude_regex = ["_templ.go", ".pb.go", ".connect.go", "node_modules/.*"]

delay = 1000
        """)

    with open("air-client.toml", "w") as f:
        f.write("""
[build]
  cmd = '''
    ./bin/templ generate &&
    bunx tailwindcss -i ./assets/css/app.css -o ./public/css/main.css &&
    ./bin/buf generate &&
    go build -o ./tmp/client cmd/client/main.go
  '''
  
  bin = "./tmp/client"
  include_ext = ["go", "templ", "proto"]
  exclude_regex = ["_templ.go", ".pb.go", ".connect.go", "node_modules/.*"]

[log]
  main_only = true
  log_only_main_loop = true

delay = 1000
        """)

    with open("taskfile.yaml", "w") as f:
        f.write(f"""
version: "3"

tasks:
  dev-client:
    cmds:
      - ./bin/air -c ./air-client.toml
    env:
      PORT: 3000
  dev-server:
    cmds:
      - ./bin/air -c ./air-server.toml
    env:
      PORT: 8080
  build-deps:
    cmds:
      - go build -o bin/deps cmd/deps/main.go
      - ./bin/deps
  build:
    cmds:
      - bunx tailwindcss -i ./assets/css/app.css -o ./public/css/main.css
      - ./bin/templ generate
      - go build -o ./bin/server cmd/server/main.go
      - go build -o ./bin/client cmd/client/main.go

    desc: "Build the Go project"
  docker-build:
    cmds:
      - docker build -t {module_name} .
  docker-run:
    cmds:
      - docker run -d -p 80:8080 --name {module_name}_container {module_name} 
  lint:
    cmds:
      - golangci-lint run
    desc: "Lint the code"

  clean:
    cmds:
      - rm -rf myapp
    desc: "Clean the build artifacts"


  """)
    os.system("go install github.com/bufbuild/buf/cmd/buf@latest")
    os.system("go install google.golang.org/protobuf/cmd/protoc-gen-go@latest")
    os.system("go install connectrpc.com/connect/cmd/protoc-gen-connect-go@latest")
    os.system("go install github.com/air-verse/air@latest")
    os.system("go install github.com/go-task/task/v3/cmd/task@latest")

    os.makedirs("cmd/deps", exist_ok=True)
    with open("cmd/deps/main.go", "w") as f:
        f.write("""
package main

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"

	"golang.org/x/sync/errgroup"
)

func main() {
	binDir, _ := filepath.Abs("./bin")
	os.Setenv("GOBIN", binDir)

	if err := os.MkdirAll(binDir, 0755); err != nil {
		fmt.Printf("🚨 Error creating bin directory: %v\n", err)
		os.Exit(1)
	}

	tools := []string{
		"github.com/bufbuild/buf/cmd/buf@latest",
		"google.golang.org/protobuf/cmd/protoc-gen-go@latest",
		"connectrpc.com/connect/cmd/protoc-gen-connect-go@latest",
		"github.com/air-verse/air@latest",
	}

	var (
		g, _  = errgroup.WithContext(context.Background())
		mu    sync.Mutex
		count int
	)

	fmt.Println("🚀 Starting parallel installation...")

	for _, tool := range tools {
		tool := tool // Capture range variable
		g.Go(func() error {
			cmd := exec.Command("go", "install", tool)

			// Capture output for cleaner display
			output, err := cmd.CombinedOutput()

			mu.Lock()
			count++
			fmt.Printf("📦 [%d/%d] %s\n", count, len(tools), tool)
			if len(output) > 0 {
				fmt.Println(string(output))
			}
			mu.Unlock()

			return err
		})
	}

	if err := g.Wait(); err != nil {
		fmt.Printf("\n❌ Installation failed: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("\n✅ Successfully installed %d tools to %s\n", len(tools), binDir)
	fmt.Println("Installed binaries:")
	files, _ := os.ReadDir(binDir)
	for _, f := range files {
		fmt.Printf(" - %s\n", f.Name())
	}
}
        """)


def setup_server(name: str):
    # Initialize Go module
    os.makedirs("cmd/server", exist_ok=True)
    # Install backend dependencies
    os.system("go get connectrpc.com/connect golang.org/x/net/http2 github.com/rs/cors")

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


def setup_client(model_path: str):
    os.makedirs("cmd/client", exist_ok=True)
    os.makedirs("internal/templates", exist_ok=True)
    os.makedirs("assets/css", exist_ok=True)
    os.makedirs("public/css", exist_ok=True)

    # Install frontend dependencies
    os.system("go get github.com/a-h/templ")
    os.system("go install github.com/a-h/templ/cmd/templ@latest")

    # Create frontend-specific files
    setup_client_templates()
    setup_client_js()
    with open("cmd/client/main.go", "w") as f:
        f.write(f"""
package main

import (
    "log"
    "net/http"
    "{model_path}/internal/services/apiv1/apiv1connect"
    "{model_path}/internal/handlers"
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
    "{model_path}/internal/services/apiv1"
    "{model_path}/internal/services/apiv1/apiv1connect"
    "{model_path}/internal/templates"
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


def setup_client_js():
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


def create_project(name: str, project_type: str, git: bool):
    module_name = name.lower().replace(" ", "-")
    module_git_path = f"github.com/itsrobel/{module_name}"
    create_shared_structure(module_name, git)
    setup_build(module_name, module_git_path if git else module_name)
    if project_type in ["backend", "fullstack"]:
        setup_server(module_git_path if git else module_name)

    if project_type in ["frontend", "fullstack"]:
        setup_client(module_git_path if git else module_name)
        os.system("./bin/templ generate")

    os.system("./bin/buf generate")


def main():
    parser = argparse.ArgumentParser(description="Generate unified project structure")
    parser.add_argument("name", help="Name of the project")
    parser.add_argument(
        "--type",
        choices=["frontend", "backend", "fullstack"],
        default="fullstack",
        help="Type of project to generate",
    )
    parser.add_argument("--no-git", action="store_false", dest="git", help="Use git")

    args = parser.parse_args()
    create_project(args.name, args.type, args.git)


if __name__ == "__main__":
    main()
