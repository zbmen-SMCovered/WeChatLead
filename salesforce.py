# 测试阶段从token获取，正式发布阶段通过浏览器获取session
from simple_salesforce import Salesforce, format_soql
import socket
import requests
import urllib
from sfenv import *

def get_code():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind(('localhost', 5000))
    serversocket.listen(5)
    serversocket.settimeout(120)  # 设置超时时间为120秒（2分钟）
    try:
        connection, address = serversocket.accept()
        buf = connection.recv(1024)
        if len(buf) > 0:
            raw = buf.decode().split(' ')[1]
            url = 'http://localhost' + raw
            url_components = urllib.parse.urlparse(url)
            authorization_code = urllib.parse.parse_qs(url_components.query)['code'][0]
            
            # 一个简单的登陆成功反馈页面
            response_text = '<html><body><h1>Login successful!</h1></body></html>'
            response_header = 'HTTP/1.1 200 OK\nContent-Type: text/html; charset=utf-8\nContent-Length: {}\n\n'.format(len(response_text))
            connection.sendall(response_header.encode())
            connection.sendall(response_text.encode())
            connection.close()
            
            return authorization_code
    except socket.timeout:
        serversocket.close()  # 当超时
        print("No connection was made within 2 minutes.")  # 引发超时错误

def get_access_token(auth_code):
    url = "https://login.salesforce.com/services/oauth2/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": "http://localhost:5000",
        "code": auth_code,
    }

    response = requests.post(url, data=payload)

    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data["instance_url"], data["refresh_token"]
    else:
        print("Error:%s"% (response.content))

def get_init(sf):

    result = sf.query_all(format_soql("SELECT Status FROM Lead where RecordTypeId='0123j000001QWVZAA4' GROUP BY Status"))
    Lead_Status_dropdown = [record['Status'] for record in result['records'] if record['Status'] is not None and record['Status'][-2:] != '_c']

    result = sf.query("SELECT WeChat_Agents_List__c FROM Lead where RecordTypeId='0123j000001QWVZAA4' GROUP BY WeChat_Agents_List__c")
    WeChat_Agents_dropdown = [record['WeChat_Agents_List__c'] for record in result['records'] if record['WeChat_Agents_List__c'] and record['WeChat_Agents_List__c'][-2:] != '_c']

    result = sf.query("SELECT WeCom_Agents_List__c FROM Lead where RecordTypeId='0123j000001QWVZAA4' GROUP BY WeCom_Agents_List__c")
    WeCom_Agents_dropdown = [record['WeCom_Agents_List__c'] for record in result['records'] if record['WeCom_Agents_List__c'] and record['WeCom_Agents_List__c'][-2:] != '_c']

    lead_description = sf.Lead.describe()
    Sales_WeChat_dropdown = []

    for field in lead_description['fields']:
        if field['name'] == 'Sales_WeChat_Account__c': 
            picklist_values = field['picklistValues']
            for picklist_value in picklist_values:
                Sales_WeChat_dropdown.append(picklist_value['label'])
    return Lead_Status_dropdown, WeChat_Agents_dropdown, WeCom_Agents_dropdown, Sales_WeChat_dropdown

def search_contact(contacts_info, sf):
    initial_values = {key: {} for key in contacts_info.keys()}

    #通过wxid 查找
    for wxid, info in contacts_info.items():
        lastname = info[0]
        result = sf.query(f"SELECT Lead_ID__c, Status, Student_or_Parent__c, LastName, Account__c, Social_Media_Platform__c, \
                            WeChat_Agents_List__c, WeCom_Agents_List__c, Sales_WeChat_Account__c, \
                            Group_Name__c, Member_First_Name__c, Member_Last_Name__c, Date_of_Birth__c, Email \
                            FROM Lead where RecordTypeId='0123j000001QWVZAA4' AND LastName = '{lastname}'")
        if result['records']:
            initial_values[wxid]["is_in_SF"] = 1
            
            leadid = result['records'][0]['Lead_ID__c']
            initial_values[wxid]["link"] =  "https://smcovered.lightning.force.com/lightning/r/Lead/%s/view"%(leadid)
            # 遍历查到的记录
            for record in result['records']:
                # 遍历记录中的每个字段
                for field in record:
                    # 跳过attributes字段，它通常包含元数据而非实际数据
                    if field != 'attributes':
                        # 将字段名作为键，字段值作为值，添加到initial_values[wxid]的字典中
                        initial_values[wxid][field] = record[field]
                        
        else:
            initial_values[wxid]["is_in_SF"] = 0
    return initial_values

def refresh_access_token(refresh_token):
    url = "https://login.salesforce.com/services/oauth2/token"
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }

    response = requests.post(url, data=payload)

    if response.status_code == 200:
        data = response.json()
        return data["access_token"], data["instance_url"]
    else:
        print("Refresh Token Error:%s"% response.content)