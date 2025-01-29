package service

import (
	"context"
	"fmt"
	"net/http"
	"zb-frontend/internal/services/apiv1"
	"zb-frontend/internal/services/apiv1/apiv1connect"
	"zb-frontend/internal/templates"

	"connectrpc.com/connect"
)

type Handlers struct {
	greetClient apiv1connect.GreetServiceClient
}

func NewHandlers(greetClient apiv1connect.GreetServiceClient) *Handlers {
	return &Handlers{
		greetClient: greetClient,
	}
}

func (h *Handlers) Index(w http.ResponseWriter, r *http.Request) {
	component := templates.Index()
	component.Render(context.Background(), w)
}

func (h *Handlers) HandleGreet(w http.ResponseWriter, r *http.Request) {
	if err := r.ParseForm(); err != nil {
		http.Error(w, "Failed to parse form", http.StatusBadRequest)
		return
	}

	name := r.FormValue("name")
	req := connect.NewRequest(&apiv1.GreetRequest{Name: name})
	fmt.Println(req)

	resp, err := h.greetClient.Greet(r.Context(), req)
	fmt.Println(resp)

	if err != nil {
		http.Error(w, "Failed to greet", http.StatusInternalServerError)
		return
	}

	component := templates.GreetingResponse(resp.Msg.Greeting)
	component.Render(r.Context(), w)
}
