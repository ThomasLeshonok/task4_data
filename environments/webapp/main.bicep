// Azure Deployment Environments definition: App Service plan + Streamlit web app.

param appName string = ''
param location string = ''

@allowed(['F1', 'B1', 'B2', 'S1', 'P0v3'])
param sku string = 'B1'
param pythonVersion string = '3.13'
param repoUrl string = ''
param branch string = 'main'
param appUsername string = 'Customer'

@secure()
param appPasswordHash string
param openAiEndpoint string = ''
param openAiDeployment string = ''

@secure()
param openAiApiKey string = ''

var name = empty(appName) ? 'task4-${uniqueString(resourceGroup().id)}' : appName
var region = empty(location) ? resourceGroup().location : location

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${name}-plan'
  location: region
  kind: 'linux'
  sku: {
    name: sku
  }
  properties: {
    reserved: true
  }
}

resource site 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: region
  kind: 'app,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|${pythonVersion}'
      appCommandLine: 'python -m streamlit run streamlit_app.py --server.port 8000 --server.address 0.0.0.0'
      webSocketsEnabled: true
      alwaysOn: sku != 'F1'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: [
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APP_USERNAME', value: appUsername }
        { name: 'APP_PASSWORD_HASH', value: appPasswordHash }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiDeployment }
        { name: 'AZURE_OPENAI_API_KEY', value: openAiApiKey }
      ]
    }
  }
}

// Public repositories only; for a private one connect Deployment Center in the portal instead.
resource source 'Microsoft.Web/sites/sourcecontrols@2024-04-01' = if (!empty(repoUrl)) {
  parent: site
  name: 'web'
  properties: {
    repoUrl: repoUrl
    branch: branch
    isManualIntegration: true
  }
}

output url string = 'https://${site.properties.defaultHostName}'
