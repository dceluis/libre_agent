# unit_registry.py

class UnitRegistry:
    units = []

    @classmethod
    def register_unit(cls, unit_class):
        cls.units.append({
            'name': unit_class.unit_name,
            'trigger_definition': unit_class.get_trigger_definition(),
            'class': unit_class
        })

    @classmethod
    def get_units(cls):
        return cls.units
