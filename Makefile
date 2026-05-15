PROFILE       ?= school
TARGET        ?= dev
APP_RESOURCE  := brfss_analytics_app
APP_NAME      := brfss-analytics

.PHONY: deploy validate bundle-deploy app-deploy grant status open help

# Default target — full pipeline in one shot
deploy: validate bundle-deploy app-deploy
	@echo ""
	@echo "==> Done. App '$(APP_NAME)' deployed via target '$(TARGET)' (profile: $(PROFILE))."
	@echo "    If this was the first deploy, run 'make grant' to grant SELECT on data_engineering.gold to the app SP."

validate:
	@echo "==> Validating bundle..."
	databricks bundle validate --target $(TARGET) --profile $(PROFILE)

bundle-deploy:
	@echo "==> Deploying bundle (uploads source + registers resources)..."
	databricks bundle deploy --target $(TARGET) --profile $(PROFILE)

app-deploy:
	@echo "==> Deploying app..."
	databricks bundle run $(APP_RESOURCE) --target $(TARGET) --profile $(PROFILE)

grant:
	@echo "==> Granting app SP SELECT on data_engineering.gold..."
	@python3 scripts/grant_app_permissions.py

status:
	databricks apps get $(APP_NAME) --profile $(PROFILE)

open:
	databricks bundle open $(APP_RESOURCE) --target $(TARGET) --profile $(PROFILE)

help:
	@echo "Usage:"
	@echo "  make                -> validate + deploy bundle + deploy app (default)"
	@echo "  make deploy         -> same as above"
	@echo "  make validate       -> validate the bundle only"
	@echo "  make bundle-deploy  -> upload source + register resources"
	@echo "  make app-deploy     -> trigger a new app deployment"
	@echo "  make grant          -> grant app SP SELECT on data_engineering.gold"
	@echo "  make status         -> show app status"
	@echo "  make open           -> open the app URL in browser"
	@echo ""
	@echo "Overrides (passed as KEY=value):"
	@echo "  PROFILE=$(PROFILE)"
	@echo "  TARGET=$(TARGET)"
