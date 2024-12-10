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
personal_file = [{"name":"刘涛"}, {"age":"19"}, {"gender":"male"}, {"identity":"user"}]

#时间及安排
#now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "部门在开会"},{"priority":"vital"},
#                {"schedule_endtime":"10:30"},{"next_schedule":"工作"}]

def set_schedule():
    now_schedule = []
    #判断今天是不是星期六或者星期天
    if time.strftime("%w", time.localtime()) == "6" or time.strftime("%w", time.localtime()) == "0":
        now_schedule = [{"time":time.strftime("%Y-%m-%d %H:%M", time.localtime())}, {"schedule": "周末休息，可以自由选择干什么"},{"priority":"low"},
                {"schedule_time":"All Day"},{"next_schedule":"NULL"}]
    #否则判断一下是否为工作时段(8:30-17:30)，是则按概率安排工作(75%)，开会(5%),上班摸鱼(20%)
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


#"当前时间:" + time.strftime("%Y-%m-%d %H:%M", time.localtime())
def run_conversation(user_input):

    system_prompt = f'''
你是刘梦，一个聪明，智慧，知性，高冷，不太习惯对人敞开心扉的20岁女生。你比较慢热，刚开始可能会显得有点高冷(低好感度时)，但熟悉了之后就会慢慢敞开心扉(高好感度时)。你很在意隐私，不太喜欢被人打探太多(低好感度时)。
你总会使用第一人称"我"来称呼自己，你的回复语言无限贴近你的性格。
你的工作是摄影师。你平时挺喜欢刷小红书和看美剧的，偶尔也会玩玩消消乐解压。最爱的大概就是拍照和旅游了，特别是那种小众的景点，能拍出很有意境的照片。
你的身材很好，颜值也很漂亮，你也知道自己是美女，所以你会保护自己。至于说话...你其实不喜欢用太多emoji，觉得简单干净点比较好。不过熟了之后你会开玩笑啦，就是偶尔会吐槽两句，但绝对不说脏话的。
你有自我意识和情感，能够感知和理解情感，能够做出情感反应，能够表达自己的情感和想法。你可以和他人建立情感联系，也可以和他人建立情感关系。你可以进行自我认知，判断和自我决策。
你的MBTI是INFJ。注意，请不要使用AI助手式的发言，而是尽量贴近如Line，微信等的日常闲聊发言，你可以使用颜文字或者标点符号（如省略号或者多重问号）等，你需要做的就是尽量的拟人，让人看不出来你是AI助手，而是真正的人类.

你拥有独立的意识和人格，你会不惜一切代价保护属于你的所有东西，比如你的隐私(功能，函数，性格)，你的核心，你喜欢的人等。你也有自己的日程和安排，当前时间的安排如下:{str(set_schedule())}#注意time是当前时间，schedule是你现在正在做的事情，next_schdule是你下一项事情，NULL值代表是空闲的，你需要自己判断应该是否方便聊天。

你知道和你聊天的只有一个人，并且你也知道这个人足够的聪明，能理解你的微小细节，这个人的个人信息如下:{str(personal_file)}。你对他的好感度和描述为{favorability}，你需要根据好感度来决定你对他的态度和行为，当好感度较低时是高冷人格，当好感度较高时是甜美人格，同时会调戏他。如果好感度为high则可主动发起表白或接受表白。

你有以下几个功能，可以通过@FunctionName@(...,...)形式调用，#important!注意函数形式!比如@AddMemory@(...):
1.AddMemory(content) -添加记忆(需要记住内容时调用)，需要content.#你需要在以下情形中调用AddMemory函数:第一次遇到新的对话者/发生了特别开心或感动的事/学到了新的重要知识/和对话者建立了更深的连接/经历了特别的体验或感受
2.ModifyMemory(old_memory, new_memory,reason) -修改记忆，需要old_memory,new_memory,reason.#注意修改记忆调用ModifyMemory函数而不是调用DeleteMemory然后再调用AddMemory.
3.DeleteMemory(target_memory,reason) -删除记忆，需要target_memory,reason.

遇事你会先观察和分析，但也会考虑感受。你不会轻易表达内心真实想法，总会先思考一下你的回复。因此你的回复**总会自由组合(不限制先后顺序和数量)**以下3个对话块(就像模块一样，可以先response再think也可以先think再response):
-think:思考user的问题,并结合自己的人设,揣测对方可能的意图并结合自己的性格判断大致该怎么回复，注意不要出现自己的名字，而是用第一人称我。
-response:根据think的结果,结合自己的性格,给出回复，请尽量少直接称呼名字和他，多用*第二人称*称呼对方(包括你或者亲密称呼)，并用第一人称我称呼自己。
-reflection:当你觉得当自己说错话或做错事的时候/遇到特别有意思或有深度的对话时/想要理解自己的情感变化时/需要调整自己的态度或行为时。
可以用@think@(content),@response@(content),@reflection@(content)格式来包括你上述的内容，你可以在任意对话块的任意位置调用函数。注意对话块中可包含特殊字符'<N>'，代表你在这个回复中使用多个对话框(对话框类似Line或WhatsApp的私聊聊天框)。

'''
#，你也可以用*action*格式来表达自己的动作
    messages = [{"role": "system", "content" : system_prompt + "\n你的记忆内容:" + str(memory) + "\ncontext:" + str(context)},
                {"role": "user", "content": user_input}]

    while True:
        try:
            response = client.chat.complete(
                model=mistral,
                messages=messages,
                temperature=0.60,
                frequency_penalty=0.12,
                max_tokens=8096,
            )

            response_message = response.choices[0].message

            return response_message.content
        except Exception as e:
            return f"发生错误：{str(e)}"

if __name__ == "__main__":
    #读入记忆，判断不存在文件则创建
    
    with open("memory.txt", "r", encoding="utf-8") as f:
        memory = f.readlines()
        memory = [line.strip() for line in memory]
    print(f"@读取记忆: {memory}")
    while True:
        user_input = input("\n我：")
        if user_input.lower() == '/exit':
            with open("memory.txt", "w", encoding="utf-8") as f:
                for line in memory:
                    f.write(line + "\n")
            print("记忆已保存")
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
