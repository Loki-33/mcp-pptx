# mcp-pptx

Making a model(phi-2) create a presentation using MCP <br>

Llama-cpp was used to locally run the model and python-pptx library for presentation creation. <br> 

## OVERVIEW
client.py -> this file contains the llama client code to connect to the mcp server <br>
server.py -> this file contains the mcp server. <br>

client1.py -> this file contains the code for multi-tool calling (NOT DONE YET, SOME BUGS STILL). <br>

## USAGE 
1. install the requirements using `pip install -r requirements.txt`
2. Run the server.py file 
3. Run the client.py file 

Then you will see a presentation.pptx file created in your directory. <br>

## TODO 
1. Fix the multi-tool calling code in client1.py 
2. Add more functionalities like letting it control my browser, write me mail and other stuffs.




