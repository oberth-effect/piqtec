from src.piqtec.controller import Controller

c = Controller("iqtec.home")
# print(list(x.do_update() for x in c.calendars.values()))
print(c.system.do_update())
