import time

from src.piqtec.system import Controller

c = Controller("iqtec.home")
b = c.sunblinds["R4_SUNBLIND_1"]

print(c.update_status())

# print(s := b.get_update())
#
# print(s.position, s.rotation)
#
# # b.set_position(0)
time.sleep(5)
# print(e := b.get_update())
# print(e.position, e.rotation)
