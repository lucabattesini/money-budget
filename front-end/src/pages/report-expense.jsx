import { useEffect, useState } from "react";
import { Center, Stack, Button, Heading, Input, Portal, Select, Box} from "@chakra-ui/react";
import { toaster, Toaster } from "../components/ui/toaster";
import { getAllCategories, insertNewTransaction } from "../api/endpoints";
import Home from "./home";

// tirar seta para baixo
// retornar feedback

export default function ReportExpense() {
    const [value, setvalue] = useState("");
    const [description, setDescription] = useState("");
    const [categories, setCategories] = useState([]);
    const [selectedCategory, setSelectedCategory] = useState("Select category");
    const [selectCategoryId, setSelectCategoryId] = useState("");

    useEffect(() => {
        getAllCategories().then(data => setCategories(data.data))
    }, []);
    
    const handleSubmit = () => {
        const formatedValue = value * 100
        const payload = {
            label: description,
            value: parseInt(formatedValue),
            category: String(selectCategoryId)
        };

        if (!value || value === 0 ) {
            toaster.create({
            title: "Error",
            type: "error",
            description: "The amount value need to be bigger than 0",
            status: "error",
            duration: 5000,
            isClosable: true,
            position: "top",
            });

            return;
        }

        if (!description) {
            toaster.create({
            title: "Error",
            type: "error",
            description: "You need to give a description to the transaction",
            status: "error",
            duration: 5000,
            isClosable: true,
            position: "top",
            });
            return;
        }

        if (!selectCategoryId) {
            toaster.create({
            title: "Error",
            type: "error",
            description: "You need to select a category to the transaction",
            status: "error",
            duration: 5000,
            isClosable: true,
            position: "top",
            });
            return;
        }

        insertNewTransaction(payload)
            .then(data => {
                console.log(data)
                if (data.status === 201 || data.status === 200) {
                    toaster.create({
                    title: "Accepted",
                    type: "success",
                    description: "Transaction saved successfully",
                    duration: 5000,
                    isClosable: true,
                    position: "top",
                    });

                    setvalue("");
                    setDescription("");
                    setSelectedCategory("Select category");

                } else {
                    toaster.create({
                    title: "Error",
                    type: "error",
                    description: "Some error ocurred to report your transaction, please try again later",
                    duration: 5000,
                    isClosable: true,
                    position: "top",
                    });
                }
            })
            .catch(error => {
                toaster.create({
                title: "Error",
                type: "error",
                description: "Some error ocurred to report your transaction, please try again later",
                duration: 5000,
                isClosable: true,
                position: "top",
                });
            })
    }
    return (
        <Center>
            <Stack
                height="100vh"
                gap={6}
                width="35vh"
                align="center"
                justify="flex-start"
                pt={20}
            >
                <Box position="absolute" right={6} top={6}>
                    <Home/>
                </Box>
                
                <Toaster/>
                
                <Heading size={"2xl"}>
                    Report Expense
                </Heading>

                <Input 
                type="number" placeholder="Amount" variant="outline" 
                value={value} onChange={(e) => setvalue(e.target.value)}
                />

                <Input
                placeholder="Description" variant="outline" maxLength={25}
                value={description} onChange={(e) => setDescription(e.target.value)}
                />

                <Select.Root>
                    <Select.HiddenSelect/>
                    <Select.Control>
                        <Select.Trigger>
                            <Select.ValueText placeholder={selectedCategory}/>
                        </Select.Trigger>
                        <Select.IndicatorGroup>
                            <Select.Indicator/>
                        </Select.IndicatorGroup>
                    </Select.Control>
                    <Portal>
                        <Select.Positioner>
                            <Select.Content>
                                {categories?.map((category) => (
                                    <Select.Item item={category.name} key={category.id} 
                                        onClick={() => {
                                            setSelectCategoryId(category.id)
                                            setSelectedCategory(category.name)
                                        }}>
                                        {category.name}
                                        <Select.Indicator/>
                                    </Select.Item>
                                ))}
                            </Select.Content>
                        </Select.Positioner>
                    </Portal>
                </Select.Root>

                <Button onClick={handleSubmit}>
                    Submit
                </Button>
            </Stack>
        </Center>
    );
}