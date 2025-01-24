import os
import sys

# Check if application name is provided
if len(sys.argv) < 2:
    print("Usage: python setup_backend.py <app-name>")
    sys.exit(1)

APP_NAME = sys.argv[1]
MODULE_NAME = APP_NAME.lower().replace(" ", "-")

# Create project structure
os.makedirs(f"{APP_NAME}-backend/cmd/server", exist_ok=True)
os.makedirs(f"{APP_NAME}-backend/internal/service", exist_ok=True)
os.makedirs(f"{APP_NAME}-backend/proto/apiv1", exist_ok=True)
os.makedirs(f"{APP_NAME}-backend/gen", exist_ok=True)

os.chdir(f"{APP_NAME}-backend")

# Initialize Go module
os.system(f"go mod init {MODULE_NAME}-backend")

# Install dependencies
os.system("go mod tidy")
os.system("go get connectrpc.com/connect golang.org/x/net/http2 github.com/rs/cors")
os.system("go install github.com/bufbuild/buf/cmd/buf@latest")

# Create proto file
with open("proto/apiv1/service.proto", "w") as f:
    f.write(f"""
syntax = "proto3";

package apiv1;
option go_package = "{MODULE_NAME}-backend/internal/services/apiv1";

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
with open("internal/service/greet.go", "w") as f:
    f.write(f"""
package service

import (
    "context"
    "fmt"
    apiv1 "{MODULE_NAME}-backend/internal/services/apiv1"
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

# Create server implementation
with open("cmd/server/main.go", "w") as f:
    f.write(f"""
package main

import (
    "log"
    "net/http"
    "{MODULE_NAME}-backend/internal/services/apiv1/apiv1connect"
    "{MODULE_NAME}-backend/internal/service"
    "github.com/rs/cors"
)

func main() {{
    mux := http.NewServeMux()
    
    // Initialize gRPC service
    greetServer := service.NewGreetServer()
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

# Create Makefile
with open("Makefile", "w") as f:
    f.write("""
.PHONY: generate build run

generate:
	buf generate

build: generate
	go build -o bin/server cmd/server/main.go

run:
	go run cmd/server/main.go
""")

# Create gitignore
with open(".gitignore", "w") as f:
    f.write("""
bin/
gen/
""")

# Generate code
os.system("buf generate")

print("Backend setup complete!")
print("Run 'make run' to start the Connect RPC server")
