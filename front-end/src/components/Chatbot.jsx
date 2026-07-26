import { useState, useRef, useEffect } from "react";
import { Flex, Box, Text, Input, IconButton, Stack } from "@chakra-ui/react";
import { LuSend } from "react-icons/lu";
import { getMe } from "../api/endpoints";
import { getToken } from "../lib/auth";

export default function Chatbot() {
    const [messages, setMessages] = useState([
        { sender: "bot", text: "Olá! Como posso te ajudar hoje?" }
    ]);
    const [inputValue, setInputValue] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const [userPhone, setUserPhone] = useState("");
    const messagesEndRef = useRef(null);

    useEffect(() => {
        const fetchUser = async () => {
            const token = getToken();
            if (token) {
                const userData = await getMe(token);
                if (userData && userData.data && userData.data.whatsapp_phone) {
                    setUserPhone(userData.data.whatsapp_phone);
                }
            }
        };
        fetchUser();
    }, []);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSendMessage = async () => {
        if (!inputValue.trim()) return;

        const userMessage = inputValue.trim();
        setMessages(prev => [...prev, { sender: "user", text: userMessage }]);
        setInputValue("");
        setIsLoading(true);

        const payload = {
            entry: [
                {
                    changes: [
                        {
                            value: {
                                messages: [
                                    {
                                        from: userPhone || "00000000000",
                                        text: {
                                            body: userMessage
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        };

        try {
            const apiUrl = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
            const response = await fetch(`${apiUrl}/webhook/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            
            if (response.ok && data.reply) {
                setMessages(prev => [...prev, { sender: "bot", text: data.reply }]);
            } else {
                setMessages(prev => [...prev, { sender: "bot", text: "Desculpe, ocorreu um erro ao processar sua mensagem." }]);
            }

        } catch (error) {
            console.error("Error sending message:", error);
            setMessages(prev => [...prev, { sender: "bot", text: "Erro de conexão ao tentar enviar a mensagem." }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === "Enter") {
            handleSendMessage();
        }
    };

    return (
        <Flex 
            direction="column" 
            flex="1" 
            w="full" 
            maxW="3xl"
            mx="auto"
            bg="transparent" 
            overflow="hidden"
        >
            {/* Messages Area */}
            <Box flex="1" overflowY="auto" p={4} bg="transparent">
                <Stack gap={4}>
                    {messages.map((msg, index) => {
                        const isUser = msg.sender === "user";
                        return (
                            <Flex key={index} justify={isUser ? "flex-end" : "flex-start"}>
                                <Box
                                    maxW="75%"
                                    bg={isUser ? "white" : "gray.700"}
                                    color={isUser ? "black" : "white"}
                                    px={4}
                                    py={2}
                                    borderRadius="xl"
                                    borderBottomRightRadius={isUser ? "sm" : "xl"}
                                    borderBottomLeftRadius={isUser ? "xl" : "sm"}
                                    boxShadow="md"
                                >
                                    <Text fontSize="sm" whiteSpace="pre-wrap">{msg.text}</Text>
                                </Box>
                            </Flex>
                        );
                    })}
                    {isLoading && (
                        <Flex justify="flex-start">
                            <Box bg="gray.700" color="gray.300" px={4} py={2} borderRadius="xl" borderBottomLeftRadius="sm">
                                <Text fontSize="sm">Digitando...</Text>
                            </Box>
                        </Flex>
                    )}
                    <div ref={messagesEndRef} />
                </Stack>
            </Box>

            {/* Input Area */}
            <Flex p={6} bg="transparent" gap={4} align="center">
                <Input
                    flex="1"
                    placeholder="Digite sua mensagem..."
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyPress={handleKeyPress}
                    bg="transparent"
                    border="1px solid"
                    borderColor="gray.700"
                    color="white"
                    _focus={{ boxShadow: "none", borderColor: "white" }}
                />
                <IconButton
                    aria-label="Send message"
                    colorScheme="gray"
                    bg="white"
                    color="black"
                    _hover={{ bg: "gray.200" }}
                    onClick={handleSendMessage}
                    disabled={isLoading || !inputValue.trim()}
                    borderRadius="full"
                >
                    <LuSend />
                </IconButton>
            </Flex>
        </Flex>
    );
}
