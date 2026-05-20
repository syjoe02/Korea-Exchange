from django.contrib import admin

from .models import KospiData, StockQueryLog


@admin.register(KospiData)
class KospiDataAdmin(admin.ModelAdmin):
    list_display = ("date", "open_price", "high_price", "low_price", "close_price", "volume")
    ordering = ("-date",)
    search_fields = ("date",)


@admin.register(StockQueryLog)
class StockQueryLogAdmin(admin.ModelAdmin):
    list_display = ("query", "created_at")
    ordering = ("-created_at",)
    search_fields = ("query",)
