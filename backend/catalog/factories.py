import factory

from companies.factories import CompanyFactory

from .models import Product


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    company = factory.SubFactory(CompanyFactory)
    name = factory.Sequence(lambda n: f"Producto {n}")
    sku = None
    unit = Product.Unit.UNIDAD
    default_price = "1000.00"
    default_cost = "600.00"
    low_stock_threshold = "0"
    current_stock = "0"
