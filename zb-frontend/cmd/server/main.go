package main

import (
	"log"
	"net/http"
	"zb-frontend/internal/service"
	"zb-frontend/internal/services/apiv1/apiv1connect"

	"github.com/rs/cors"
)

func main() {
	mux := http.NewServeMux()

	// Initialize HTTP client for internal gRPC calls
	client := apiv1connect.NewGreetServiceClient(
		http.DefaultClient,
		"http://localhost:50051",
	)

	// Initialize handlers
	handlers := service.NewHandlers(client)

	// Routes
	mux.HandleFunc("/", handlers.Index)
	mux.HandleFunc("/greet", handlers.HandleGreet)

	// Serve static files

	// Configure CORS

	// Serve static files
	fs := http.FileServer(http.Dir("assets"))
	mux.Handle("/assets/", http.StripPrefix("/assets/", fs))

	// Configure CORS
	corsHandler := cors.New(cors.Options{
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{"GET", "POST", "OPTIONS"},
		AllowedHeaders: []string{"Accept", "Content-Type", "Connect-Protocol-Version"},
	})

	wrappedHandler := corsHandler.Handler(mux)

	log.Println("Server starting on :3000")
	if err := http.ListenAndServe(":3000", wrappedHandler); err != nil {
		log.Fatal(err)
	}
}
