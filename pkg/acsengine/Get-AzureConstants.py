#!/usr/bin/python

from time import gmtime, strftime
import subprocess
import json

time = strftime("%Y-%m-%d %H:%M:%S", gmtime())

def getAllSizes():
    locations = json.loads(subprocess.check_output(['az', 'account', 'list-locations']))
    sizeMap = {}

    for location in locations:
        sizes = json.loads(subprocess.check_output(['az', 'vm', 'list-sizes', '-l', location['name']]))
        for size in sizes:
            if not size['name'] in sizeMap and not size['name'].split('_')[0] == 'Basic':
                sizeMap[size['name']] = size

    return sizeMap

min_cores = 2
dcos_masters_ephemeral_disk_min = 102400

def getDcosMasterMap(sizeMap):
    masterMap = {}

    for key in sizeMap.keys():
        size = sizeMap[key]
        if size['numberOfCores'] >= min_cores and \
           size['resourceDiskSizeInMb'] >= dcos_masters_ephemeral_disk_min:
            masterMap[size['name']] = size

    return masterMap

def getMasterAgentMap(sizeMap):
    agentMap = {}

    for key in sizeMap.keys():
        size = sizeMap[key]
        if size['numberOfCores'] >= min_cores:
            agentMap[size['name']] = size

    return agentMap

def getLocations():
    locations = json.loads(subprocess.check_output(['az', 'account', 'list-locations']))

    locationList = [l['name'] for l in locations]

    #hard code Azure China Cloud location
    locationList.append('chinanorth')
    locationList.append('chinaeast')
    # Adding two Canary locations
    locationList.append('centraluseuap')
    locationList.append('eastus2euap')

    locationList = sorted(locationList)
    return locationList

def getStorageAccountType(sizeName):
    capability = sizeName.split('_')[1]
    if 'S' in capability or 's' in capability:
        return "Premium_LRS"
    else:
        return "Standard_LRS"

def getFileContents(dcosMasterMap, masterAgentMap, kubernetesAgentMap, sizeMap, locations):
    text = r"""package acsengine

import "fmt"

// AUTOGENERATED FILE - last generated """ + time

    text += r"""

const (
       // AzurePublicProdFQDNFormat specifies the format for a prod dns name
       AzurePublicProdFQDNFormat = "%s.%s.cloudapp.azure.com"
       //AzureChinaProdFQDNFormat specify the endpoint of Azure China Cloud
       AzureChinaProdFQDNFormat = "%s.%s.cloudapp.chinacloudapi.cn"
)

// AzureLocations provides all azure regions in prod.
// Related powershell to refresh this list:
//   Get-AzureRmLocation | Select-Object -Property Location
var AzureLocations = []string{
"""
    for location in locations:
        text += '        "' + location + '",' + '\n'

    text += r"""}

// FormatAzureProdFQDNs constructs all possible Azure prod fqdn
func FormatAzureProdFQDNs(fqdnPrefix string) []string {
        var fqdns []string
        for _, location := range AzureLocations {
                fqdns = append(fqdns, FormatAzureProdFQDN(fqdnPrefix, location))
        }
        return fqdns
}

// FormatAzureProdFQDN constructs an Azure prod fqdn
func FormatAzureProdFQDN(fqdnPrefix string, location string) string {
        FQDNFormat := AzurePublicProdFQDNFormat
        if location == "chinaeast" || location == "chinanorth" {
                FQDNFormat = AzureChinaProdFQDNFormat
        }
        return fmt.Sprintf(FQDNFormat, fqdnPrefix, location)
}

// GetDCOSMasterAllowedSizes returns the master allowed sizes
func GetDCOSMasterAllowedSizes() string {
        return `      "allowedValues": [
"""
    dcosMasterMapKeys = sorted(dcosMasterMap.keys())
    for key in dcosMasterMapKeys[:-1]:
        text += '        "' + key + '",\n'
    text += '        "' + dcosMasterMapKeys[-1] + '"\n'

    text += r"""    ],
`
}

// GetMasterAgentAllowedSizes returns the agent allowed sizes
func GetMasterAgentAllowedSizes() string {
        return `      "allowedValues": [
"""
    masterAgentMapKeys = sorted(masterAgentMap.keys())
    for key in masterAgentMapKeys[:-1]:
        text += '        "' + key + '",\n'
    text += '        "' + masterAgentMapKeys[-1] + '"\n'
    text += r"""    ],
`
}

// GetKubernetesAgentAllowedSizes returns the allowed sizes for Kubernetes agent
func GetKubernetesAgentAllowedSizes() string {
        return `      "allowedValues": [
"""
    kubernetesAgentMapKeys = sorted(kubernetesAgentMap.keys())
    for key in kubernetesAgentMapKeys[:-1]:
        text += '        "' + key + '",\n'
    text += '        "' + kubernetesAgentMapKeys[-1] + '"\n'
    text += r"""    ],
`
}

// GetSizeMap returns the size / storage map
func GetSizeMap() string {
    return `    "vmSizesMap": {
"""
    mergedMap = {}
    for key in kubernetesAgentMapKeys:
        size = kubernetesAgentMap[key]
        if not key in mergedMap:
            mergedMap[size['name']] = size

    mergedMapKeys = sorted(mergedMap.keys())
    for key in mergedMapKeys[:-1]:
        size = mergedMap[key]
        text += '    "' + size['name'] + '": {\n'
        storageAccountType = getStorageAccountType(size['name'])
        text += '      "storageAccountType": "' + storageAccountType + '"\n    },\n'

    key = mergedMapKeys[-1]
    size = mergedMap[key]
    text += '    "' + size['name'] + '": {\n'
    storageAccountType = getStorageAccountType(size['name'])
    text += '      "storageAccountType": "' + storageAccountType + '"\n    }\n'

    text += r"""   }
`
}

// GetClassicAllowedSizes returns the classic allowed sizes
func GetClassicAllowedSizes() string {
        return `      "allowedValues": [
"""
    sizeMapKeys = sorted(sizeMap.keys())
    for key in sizeMapKeys[:-1]:
        text += '        "' + sizeMap[key]['name'] + '",\n'
    key = sizeMapKeys[-1]
    text += '        "' + sizeMap[key]['name'] + '"\n'

    text += r"""    ],
`
}

// GetClassicSizeMap returns the size / storage map
func GetClassicSizeMap() string {
    return `    "vmSizesMap": {
"""
    sizeMapKeys = sorted(sizeMap.keys())
    for key in sizeMapKeys[:-1]:
        text += '        "' + sizeMap[key]['name'] + '": {\n'
        storageAccountType = getStorageAccountType(size['name'])
        text += '      "storageAccountType": "' + storageAccountType + '"\n    },\n'
    key = sizeMapKeys[-1]
    text += '        "' + sizeMap[key]['name'] + '": {\n'
    storageAccountType = getStorageAccountType(size['name'])
    text += '      "storageAccountType": "' + storageAccountType + '"\n    }\n'

    text += r"""   }
`
}"""
    return text


def main():
    outfile = 'pkg/acsengine/azureconst.go'
    allSizes = getAllSizes()
    dcosMasterMap = getDcosMasterMap(allSizes)
    masterAgentMap = getMasterAgentMap(allSizes)
    kubernetesAgentMap = allSizes
    locations = getLocations()
    text = getFileContents(dcosMasterMap, masterAgentMap, kubernetesAgentMap, allSizes, locations)

    with open(outfile, 'w') as f:
        f.write(text)

    subprocess.check_call(['gofmt', '-w', outfile])

if __name__ == '__main__':
    main()