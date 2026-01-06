from utils.api_helper import NorenApiPy
import logging

#enable dbug to see request and responses
logging.basicConfig(level=logging.DEBUG)

#start of our program
api = NorenApiPy()

#set token and user id
#paste the token generated using the login flow described 
# in LOGIN FLOW of https://pi.flattrade.in/docs
usersession='03514367a294fd228af0e955424a4f48d2a11a81e927a2fa58e5f7d97194d672'
userid = 'FZ31397'

ret = api.set_session(userid= userid, password = '', usertoken= usersession)

print(ret)