from utils.api_helper import NorenApiPy
import logging

#enable dbug to see request and responses
logging.basicConfig(level=logging.DEBUG)

#start of our program
api = NorenApiPy()

#set token and user id
#paste the token generated using the login flow described 
# in LOGIN FLOW of https://pi.flattrade.in/docs
usersession='a318678a850c0467132b857b2f8ab38811708d950c3a68d54029d94b2bd875a9'
userid = 'FZ31397'

ret = api.set_session(userid= userid, password = '', usertoken= usersession)

print(ret)