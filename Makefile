.PHONY: render-platform render-apps
render-platform:
	kubectl kustomize environments/local/platform
render-apps:
	kubectl kustomize environments/local/apps
