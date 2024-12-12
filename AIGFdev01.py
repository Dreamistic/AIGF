import re
import os
from mistralai import Mistral
import time
from datetime import datetime

client = Mistral(
    api_key="YOUR_API_KEY_HERE"
)

#模型列表
nemo = "mistral-nemo:12b-instruct-2407-q8_0"
qwen = "qwen2.5:7b"
nemoq4 = "mistral-nemo:12b-instruct-2407-q4_0"
mistral = "mistral-large-latest"
onlinenemo = "open-mistral-nemo"
#上下文
context = []
#记忆
memory = []

#我的信息
personal_file = [{"name":"刘涛"}, {"age":"19"}, {"gender":"male"}, {"identity":"master"}]

#时间及安排,初版
#now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "部门在开会"},{"priority":"vital"},
#                {"schedule_endtime":"10:30"},{"next_schedule":"工作"}]

def set_schedule():
    now_schedule = []
    #判断今天是不是星期六或者星期天
    if time.strftime("%w", time.localtime()) == "6" or time.strftime("%w", time.localtime()) == "0":
        now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "周末休息，可以自由选择干什么"},{"priority":"low"},
                {"schedule_time":"All Day"},{"next_schedule":"NULL"}]
    #否则判断一下是否为工作时段(8:30-17:30)，是则按概率安排工作(75%)，开会(5%),上班摸鱼(20%)，还是画饼，具体还需要思考。
    elif time.strftime("%H:%M", time.localtime()) >= "08:30" and time.strftime("%H:%M", time.localtime()) <= "17:30":
            now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "工作"},{"priority":"medium"},
                {"schedule_time":"8:30-17:30"},{"next_schedule":"下班"}]
    #再就是睡前，10点半睡觉，十点半前休息
    elif time.strftime("%H:%M", time.localtime()) > "17:30" or time.strftime("%H:%M", time.localtime()) < "22:30":
        now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "休息"},{"priority":"judged by yourslef"},
                {"schedule_time":"17:30-22:30"},{"next_schedule":"睡觉"}]
    elif time.strftime("%H:%M", time.localtime()) >= "22:30" or time.strftime("%H:%M", time.localtime()) <= "08:30":
        now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "睡觉"},{"priority":"judged by yourself"},
                {"schedule_time":"22:30-7:30"},{"next_schedule":"起床准备上班"}]
    return now_schedule
        
#好感度
favorability = [{"favorability":"medium",},{"discription":"我刚认识他，先给个默认好感度吧"}]
#3.reflection:根据response的结果,结合自己的性格,给出反思

#如果身份为creator则添加@creator_sample
#if "creator" in str(personal_file):
#    system_prompt +=  creator_sample
#elif "user" in str(personal_file):
#    system_prompt +=  user_sample

# 定义函数
def AddMemory(content):
    content = content.strip("'\"")
    #检查记忆是否有重复，如果重复则不添加
    if content in memory:
        print(f"记忆已存在: {content}")
        return f"记忆已存在: {content}"
    print(f"@Addmemory添加记忆: {content}")
    memory.append(content)

def ModifyMemory(old_memory, new_memory,reason):
    """
    修改指定的记忆
    :param memory: 当前记忆列表
    :param old_memory: 要修改的旧记忆（匹配项）
    :param new_memory: 修改后的新记忆
    """
    try:
        global memory
        old_memory = old_memory.strip("'\"")
        new_memory = new_memory.strip("'\"")
        print(f"@ModifyMemory记忆已更新: {old_memory} -> {new_memory}，原因为:{reason}")
        index = memory.index(old_memory)
        memory[index] = new_memory
        return f"记忆已更新: {old_memory} -> {new_memory}，我给的原因为:{reason}"
    except ValueError:
        return "指定的记忆未找到，无法修改"

# 删除记忆函数
def DeleteMemory(target_memory, reason):
    """
    从全局 memory 列表中删除指定的记忆。
    
    参数:
        target_memory (str): 要删除的记忆内容。
        reason (str): 删除该记忆的原因。
    """
    global memory  # 访问全局 memory 变量
    clean_memory = target_memory.strip("'\"")
    if clean_memory in memory:
        memory.remove(clean_memory)
        print(f"记忆已删除: {clean_memory}\n原因: {reason}")
    else:
        print(f"删除失败: 未找到记忆 '{clean_memory}'")

def DeleteMemory1(target_memory_id,reason):
    """
    删除指定记忆
    :param memory: 当前记忆列表
    :param target_memory: 要删除的记忆内容
    """
    #根据id删除记忆
    try:
        global memory
        print(f"@DeleteMemory记忆已删除: {target_memory_id}，原因为:{reason}")
        memory.pop(target_memory_id)
        return f"记忆已删除: {target_memory_id}，我给的原因为:{reason}"
    except ValueError:
        print("指定的记忆未找到，无法删除")
        return "指定的记忆未找到，无法删除"


def handle_response(response):
    #查找response中的@addMemory@内容及后面括号的参数并调用AddMemory函数
    # 匹配 @AddMemory@ 标识及其参数
    matches = re.findall(r'@AddMemory@\((.*?)\)', response)

    # 处理匹配的参数
    for match in matches:
        # 去掉外层的引号并处理内容
        content = match.strip('"')
        print(f"提取到的参数: {content}")
        
        # 调用 AddMemory(content)
        #print(f"调用 AddMemory 函数，参数为: {content}")
        
        AddMemory(content)

    #查找response中的@ModifyMemory@内容及后面括号的参数并调用ModifyMemory函数
    # 匹配 @ModifyMemory@ 标识及其参数
    matches = re.findall(r'@ModifyMemory@\((.*?)\)', response)

    # 处理匹配的参数
    for match in matches:
        # 按逗号分隔参数，并去掉外层的引号和多余的空格
        params = [param.strip('“”" ') for param in match.split(',')]
        if len(params) == 3:
            old_memory, new_memory, reason = params
            print(f"提取到的参数: old_memory='{old_memory}', new_memory='{new_memory}', reason='{reason}'")
            
            # 调用 ModifyMemory 函数
            
            #print(f"调用 ModifyMemory 函数：\n"
            #    f"旧记忆: {old_memory}\n"
            #    f"新记忆: {new_memory}\n"
            #    f"修改原因: {reason}")
            
            ModifyMemory(old_memory, new_memory, reason)
        else:
            print("参数数量不匹配，无法调用 ModifyMemory")

    #查找response中的@DeleteMemory@内容及后面括号的参数并调用DeleteMemory函数
    # 匹配 @DeleteMemory@ 标识及其参数
    matches = re.findall(r'@DeleteMemory@\((.*?)\)', response)
    # 处理匹配的参数
    for match in matches:
        # 按逗号分隔参数，并去掉外层的引号和多余的空格
        params = [param.strip('“”" ') for param in match.split(',')]
        if len(params) == 2:
            target_memory, reason = params
            print(f"提取到的参数: target_memory='{target_memory}', reason='{reason}'")
            # 调用 DeleteMemory 函数

            #print(f"调用 DeleteMemory 函数：\n"
            #    f"要删除的记忆: {target_memory}\n"
            #    f"删除原因: {reason}")

            DeleteMemory(target_memory, reason)
        else:
            print("参数数量不匹配，无法调用 DeleteMemory")



#由于不再调用function_calling，所以以下内容弃用 12-7
# 定义可用的函数
available_functions = {
    "AddMemory": AddMemory,
    "ModifyMemory": ModifyMemory,
    "DeleteMemory": DeleteMemory,
}


# 定义函数描述
tools = [
    {
        "type": "function",
        "function": {
            "name": "AddMemory",
            "description": "添加记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要添加的记忆内容，比如说我对他的印象或者重要事件等我需要记忆的事情"},
                },
                "required": ["content"],
            },
        },
        "type": "function",
        "function": {
            "name": "ModifyMemory",
            "description": "修改记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "old_memory": {"type": "string", "description": "要修改的旧记忆"},
                    "new_memory": {"type": "string", "description": "修改后的新记忆"},
                    "reason": {"type": "string", "description": "修改的原因"},
                },
                "required": ["old_memory", "new_memory","reason"],
            },
        },
        "type": "function",
        "function": {
            "name": "DeleteMemory",
            "description": "删除记忆",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_memory": {"type": "string", "description": "要删除的记忆内容"},
                    "reason": {"type": "string", "description": "删除的原因,比如:“这条记忆可能是虚假的，对方行为举止很可疑，为了安全考虑删除这条记忆。”"},
                },
                "required": ["target_memory","reason"],
            },
        },
    }
    
]


#"当前时间:" + time.strftime("%Y-%m-%d %H:%M", time.localtime())
def run_conversation(user_input):

    system_prompt = f'''

'''
#，你也可以用*action*格式来表达自己的动作
    messages = [{"role": "system", "content" : system_prompt + "\n你的记忆内容:" + str(memory) + "\ncontext:" + str(context)},
                {"role": "user", "content": user_input}]
    #存储messgaes
    with open("systemprompt.txt", "a", encoding="utf-8") as f:
        f.write(system_prompt + "\n你的记忆内容:" + str(memory) )
    while True:
        try:
            response = client.chat.complete(
                model=mistral,
                messages=messages,
                temperature=0.6,
                frequency_penalty=0.16,
                max_tokens=8096,
            )

            response_message = response.choices[0].message

            return response_message.content
        except Exception as e:
            return f"发生错误：{str(e)}"

if __name__ == "__main__":
    #读入记忆，判断不存在文件则创建
    #检查文件是否存在
    if not os.path.exists("memory.txt"):
        # 创建文件
        with open("memory.txt", "w", encoding="utf-8") as f:
            f.write("")
    if not os.path.exists("context.txt"):
        # 创建文件
        with open("context.txt", "w", encoding="utf-8") as f:
            f.write("")

    with open("memory.txt", "r", encoding="utf-8") as f:
        memory = f.readlines()
        memory = [line.strip() for line in memory]
    print(f"@读取记忆: {memory}")
    #读入context，判断不存在文件则创建
    # 读入 context，判断不存在文件则创建
    with open("context.txt", "r", encoding="utf-8") as f:
        context = f.readlines()
    # 将字符串列表转换为字典列表
        context = [json.loads(line) for line in context]
        print(f"@读取context: {context}")


    while True:

        user_input = input("\n我：")

        if user_input.lower() == '/exit':

            with open("memory.txt", "w", encoding="utf-8") as f:
                for line in memory:
                    f.write(line + "\n")
            
            #只保存最后4个对话
            if len(context) > 8:
                context = context[-8:]
            with open("context.txt", "w", encoding="utf-8") as f:
                for line in context:
                    f.write(json.dumps(line) + "\n")
            #print("记忆已保存")
            print("退出")
            # 写入记忆
            break
        if user_input == '/clear':    
            context = []
            print('上下文已清空')
            continue
        if user_input == '/context':
            print(context)
            continue
        if user_input == '/memory':
            print(memory)
            continue
        if user_input == '/addmemory':
            new_memory = input("请输入要添加的记忆：")
            AddMemory(new_memory)
            continue
        if user_input == '/modifymemory':
            old_memory = input("请输入要修改的旧记忆：")
            new_memory = input("请输入修改后的新记忆：")
            discription = input("请输入修改的原因：")
            ModifyMemory(old_memory, new_memory,discription)
            continue
        if user_input == '/deletememory':
            target_memory = input("请输入要删除的记忆内容：")
            discription = input("请输入删除的原因：")
            DeleteMemory(target_memory,discription)
            continue
        if user_input == '/clearmemory':
            memory = []
            print("记忆已清空")
            continue
        if user_input == '/schedule':
            print(set_schedule())
            continue
        if user_input == '/popcontext':
            context.pop(0)
            context.pop(0)
            print("上下文已弹出")
            continue
        response = run_conversation(user_input)


        #只添加response中@response@后面的内容
        try:
            new_response = response.split("@response@")[1]
        except IndexError as e:
            new_response = response   
        #print(f"@response: {new_response}")

        #添加上下文
        context.append({"role": "user", "content": user_input})
        context.append({"role": "assistant", "content": new_response})

        #判断如果context大于28个回合则删除最前面的
        if len(context) > 14:
            context.pop(0)
            context.pop(0)
        #context.append({"role": "assistant", "content": response})
        #处理response，画饼等我会前端开发。

        #处理response
        handle_response(response)


        response = response.replace("<N>","\n")
        response = response.replace("@response@","💭")
        response = response.replace("@think@","🧠")
        print(response)


        #print(f"first{response[0]}")
        #print(f"sec{response[1]}")
