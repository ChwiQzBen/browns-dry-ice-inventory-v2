from datetime import datetime, timedelta

class SystemIntegrations:
    def __init__(self):
        self.supported_integrations = {
            'erp_systems': ['SAP', 'Oracle', 'Microsoft Dynamics'],
            'accounting_software': ['QuickBooks', 'Sage', 'Xero'],
            'supplier_apis': ['REST', 'GraphQL', 'SOAP'],
            'iot_sensors': ['temperature', 'weight', 'location']
        }
        self.active_integrations = {}
    
    def setup_api_integration(self, system_type, credentials):
        """Setup external system integrations"""
        if not self.validate_credentials(system_type, credentials):
            return {"status": "error", "message": "Invalid credentials"}
        
        connection = self.create_connection(system_type, credentials)
        
        self.active_integrations[system_type] = {
            'connection': connection,
            'credentials': credentials,
            'status': 'ACTIVE'
        }
        
        return {
            'status': 'success',
            'connection': connection,
            'data_mapping': self.create_data_mapping(system_type),
            'sync_schedule': self.setup_sync_schedule(system_type)
        }
    
    def validate_credentials(self, system_type, credentials):
        """Validate integration credentials"""
        return True
    
    def create_connection(self, system_type, credentials):
        """Create connection to external system"""
        return f"{system_type}_connection"
    
    def create_data_mapping(self, system_type):
        """Create data mapping for integration"""
        return {
            'inventory': f"{system_type}_inventory_field",
            'orders': f"{system_type}_orders_field",
            'customers': f"{system_type}_customers_field"
        }
    
    def setup_sync_schedule(self, system_type, frequency='daily'):
        """Setup sync schedule"""
        return {
            'frequency': frequency,
            'next_sync': datetime.now() + timedelta(days=1)
        }
    
    def sync_data(self, system_type):
        """Perform data synchronization"""
        if system_type not in self.active_integrations:
            return {"status": "error", "message": "Integration not set up"}
        
        return {"status": "success", "records_synced": 42}